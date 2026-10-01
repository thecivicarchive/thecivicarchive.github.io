/*
 cabin_room3d.js - the cabin: the room a visitor lands in (John, 2026-10-01). A small log cabin, seen in the first
 person and walked through: a fire, two armchairs, a lamp, a bookshelf, a window seat under a wide window, and outside
 the window the Rocky Mountains at the visitor's own time of day and season. Two posters hang beside the window and
 glow: they are the doors to the site's two spaces (On The Ballot; Legislation & Legislatures).

 The room says nothing about anyone: it holds no record and no claim, only the two doors. Each poster is also an
 ordinary link on the page, so the room is never the only way in.

 Uses three.js (MIT licence, vendor/three.module.min.js), kept with the site so nothing is fetched from anyone else's
 server. build_cabin.py copies this file beside the page and points the import below at the site's own copy.

   start(canvas, opts) -> {go(i), look(i), still(w, h, view), setWhen(name), dispose()}
     opts.posters   [{url, kicker, head, sub, cta, foot, look}]   two of them
     opts.when      "morning" | "afternoon" | "dusk" | "night"    (default: by the device's clock)
     opts.season    "winter" | "spring" | "summer" | "autumn"     (default: by the device's calendar)
     opts.calm      true = no flicker, no head bob, no walk-up: things happen at once
     opts.onHover(i)      a poster is under the pointer (-1: none)
     opts.onLeave(url)    a poster was chosen and the visitor has walked up to it
     opts.onMove()        the visitor moved or looked for the first time
   still() draws one frame to a JPEG data URL, for checking the room where frames are not being drawn.
*/
import * as THREE from "./vendor/three.module.min.js";

const W = 8.4, D = 6.6, H = 3.0, HX = W / 2, HZ = D / 2;            // the room: x across, z toward the window wall (-z), y up
const WIN = {x0: -2.1, x1: 2.1, y0: 0.82, y1: 2.62};                 // the window in the far wall
const EYE = 1.62, RADIUS = 0.32;

/* ---------- time of day and season, from the visitor's own device ---------- */
export function whenNow(d = new Date()){ const h = d.getHours() + d.getMinutes() / 60; return h < 5.5 ? "night" : h < 11 ? "morning" : h < 17 ? "afternoon" : h < 20.25 ? "dusk" : "night"; }
export function seasonNow(d = new Date()){ return ["winter", "winter", "spring", "spring", "spring", "summer", "summer", "summer", "autumn", "autumn", "autumn", "winter"][d.getMonth()]; }
const SKY = {
  morning:   {top: "#5c9be0", mid: "#b9d6f1", low: "#ffd9ba", sun: [-0.42, 0.30], disc: "#fff3d6", snow: "#ffffff", rock: "#74859a", wood: "#3f5a4a", haze: "#dce8f3", cloud: "#ffe9d6",
              hemi: [1.5, "#dfeaff", "#8a6a48"], dir: [2.2, "#ffe2b8", [-6, 5, -8]], fire: 9, lamp: 0, lantern: 0, poster: 3, stars: 0, glass: 0.05, expo: 1.0},
  afternoon: {top: "#3a82d6", mid: "#97c4ee", low: "#e2f0fb", sun: [0.36, 0.50], disc: "#fffbea", snow: "#ffffff", rock: "#6c7c92", wood: "#3a5743", haze: "#d5e6f5", cloud: "#ffffff",
              hemi: [1.9, "#e6f0ff", "#8f7250"], dir: [2.8, "#fff6e0", [4, 9, -7]], fire: 6, lamp: 0, lantern: 0, poster: 3, stars: 0, glass: 0.05, expo: 1.05},
  dusk:      {top: "#25336a", mid: "#a8648a", low: "#ffb173", sun: [0.34, 0.085], disc: "#ffd9a0", snow: "#ffc7b4", rock: "#4c4a6c", wood: "#272f3d", haze: "#d99c8c", cloud: "#ff9d7a",
              hemi: [0.75, "#bba8cc", "#5a4030"], dir: [1.0, "#ff9a5a", [5, 1.4, -9]], fire: 22, lamp: 14, lantern: 7, poster: 5, stars: 0.35, glass: 0.10, expo: 1.0},
  night:     {top: "#030716", mid: "#0a1430", low: "#18284c", sun: [-0.28, 0.42], disc: "#e9eefc", snow: "#a9b7d9", rock: "#1b2338", wood: "#0c1018", haze: "#1f2c52", cloud: "#26345c",
              hemi: [0.30, "#35426e", "#2a1c12"], dir: [0.28, "#8fa6ff", [-4, 8, -6]], fire: 27, lamp: 17, lantern: 9, poster: 6, stars: 1, glass: 0.20, expo: 1.08},
};
const LAND = {      // the ground and the trees outside, by season
  winter: {ground: "#e9eef4", pine: "#2f4a3f", pineTip: "#eef3f6", aspen: null, snowline: 0.18},
  spring: {ground: "#6f8f4e", pine: "#24503a", pineTip: "#2f6a47", aspen: "#9ac75a", snowline: 0.50},
  summer: {ground: "#5f8a45", pine: "#1f4a33", pineTip: "#2a5f40", aspen: "#6fae4c", snowline: 0.66},
  autumn: {ground: "#8a8048", pine: "#22483a", pineTip: "#2c5c43", aspen: "#f0b429", snowline: 0.46},
};

/* ---------- small tools ---------- */
function rng(seed){ let a = seed >>> 0; return () => { a |= 0; a = a + 0x6D2B79F5 | 0; let t = Math.imul(a ^ a >>> 15, 1 | a); t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t; return ((t ^ t >>> 14) >>> 0) / 4294967296; }; }
function tex(w, h, draw, repeat){
  const c = document.createElement("canvas"); c.width = w; c.height = h; draw(c.getContext("2d"), w, h);
  const t = new THREE.CanvasTexture(c); t.colorSpace = THREE.SRGBColorSpace; t.anisotropy = 4;
  if (repeat) { t.wrapS = t.wrapT = THREE.RepeatWrapping; }
  return t;
}
const std = (o) => new THREE.MeshStandardMaterial(Object.assign({roughness: 0.92, metalness: 0}, o));
function box(w, h, d, mat, x, y, z, parent){ const m = new THREE.Mesh(new THREE.BoxGeometry(w, h, d), mat); m.position.set(x, y, z); parent.add(m); return m; }
function cyl(r0, r1, h, mat, x, y, z, parent, seg = 14){ const m = new THREE.Mesh(new THREE.CylinderGeometry(r0, r1, h, seg), mat); m.position.set(x, y, z); parent.add(m); return m; }
/* a wall piece whose log pattern follows the world, so neighbouring pieces line up: u from the wall's long axis, v from height */
function wall(w, h, mat, x, y, z, ry, parent){
  const g = new THREE.PlaneGeometry(w, h), p = g.attributes.position, uv = g.attributes.uv;
  const along = Math.abs(Math.sin(ry)) > 0.5 ? z : x;
  for (let i = 0; i < p.count; i++) uv.setXY(i, (p.getX(i) + along) / 3.1, (p.getY(i) + y) / 0.94);
  const m = new THREE.Mesh(g, mat); m.position.set(x, y, z); m.rotation.y = ry; parent.add(m); return m;
}
function wrap(ctx, text, x, y, maxW, lineH, align = "left"){
  const words = String(text).split(/\s+/); let line = "", yy = y; ctx.textAlign = align;
  for (const w of words) { const t = line ? line + " " + w : w; if (ctx.measureText(t).width > maxW && line) { ctx.fillText(line, x, yy); line = w; yy += lineH; } else line = t; }
  if (line) ctx.fillText(line, x, yy);
  return yy + lineH;
}

/* ---------- textures, drawn here so the room needs no picture files ---------- */
function logsTexture(){
  return tex(512, 512, (c, w, h) => { const r = rng(7), n = 6, lh = h / n;
    for (let i = 0; i < n; i++) { const y = i * lh, g = c.createLinearGradient(0, y, 0, y + lh), warm = 0.92 + r() * 0.16;
      const col = (a, b, d) => `rgb(${Math.round(a * warm)},${Math.round(b * warm)},${Math.round(d * warm)})`;
      g.addColorStop(0, col(70, 42, 22)); g.addColorStop(0.18, col(150, 100, 58)); g.addColorStop(0.5, col(176, 122, 72)); g.addColorStop(0.85, col(128, 84, 46)); g.addColorStop(1, col(58, 34, 18));
      c.fillStyle = g; c.fillRect(0, y, w, lh);
      for (let k = 0; k < 26; k++) { c.strokeStyle = `rgba(60,34,16,${0.05 + r() * 0.12})`; c.lineWidth = 0.6 + r() * 1.4; const yy = y + 6 + r() * (lh - 12); c.beginPath(); c.moveTo(0, yy); c.bezierCurveTo(w * 0.3, yy + (r() - 0.5) * 6, w * 0.7, yy + (r() - 0.5) * 6, w, yy); c.stroke(); }
      for (let k = 0; k < 2; k++) if (r() < 0.6) { const kx = r() * w, ky = y + lh * (0.3 + r() * 0.4); c.fillStyle = "rgba(64,36,18,.55)"; c.beginPath(); c.ellipse(kx, ky, 7 + r() * 6, 4 + r() * 3, 0, 0, 7); c.fill(); }
      c.fillStyle = "rgba(28,16,8,.85)"; c.fillRect(0, y + lh - 3, w, 3); }
  }, true);
}
function planksTexture(){
  return tex(512, 512, (c, w, h) => { const r = rng(11), n = 7, pw = w / n;
    for (let i = 0; i < n; i++) { const t = 0.86 + r() * 0.22; c.fillStyle = `rgb(${Math.round(148 * t)},${Math.round(104 * t)},${Math.round(62 * t)})`; c.fillRect(i * pw, 0, pw, h);
      for (let k = 0; k < 22; k++) { c.strokeStyle = `rgba(70,42,20,${0.05 + r() * 0.1})`; c.lineWidth = 0.6 + r(); const xx = i * pw + 3 + r() * (pw - 6); c.beginPath(); c.moveTo(xx, 0); c.bezierCurveTo(xx + (r() - 0.5) * 5, h * 0.3, xx + (r() - 0.5) * 5, h * 0.7, xx, h); c.stroke(); }
      c.fillStyle = "rgba(30,18,8,.7)"; c.fillRect(i * pw, 0, 2, h); const cut = r() * h; c.fillRect(i * pw, cut, pw, 2); }
  }, true);
}
function stoneTexture(){
  return tex(256, 256, (c, w, h) => { const r = rng(23); c.fillStyle = "#5f5a53"; c.fillRect(0, 0, w, h);
    for (let row = 0; row < 6; row++) { let x = -r() * 30; const y = row * (h / 6), rh = h / 6 - 5;
      while (x < w) { const sw = 34 + r() * 46, t = 0.8 + r() * 0.35; c.fillStyle = `rgb(${Math.round(142 * t)},${Math.round(134 * t)},${Math.round(124 * t)})`;
        c.beginPath(); c.roundRect(x + 2, y + 3, sw - 5, rh, 9); c.fill(); c.fillStyle = "rgba(255,255,255,.07)"; c.fillRect(x + 6, y + 6, sw - 14, 4); x += sw; } }
  }, true);
}
function rugTexture(){
  return tex(512, 368, (c, w, h) => { c.fillStyle = "#7a2e22"; c.fillRect(0, 0, w, h); c.fillStyle = "#e9dcc0"; c.fillRect(18, 18, w - 36, h - 36); c.fillStyle = "#23395b"; c.fillRect(30, 30, w - 60, h - 60);
    c.fillStyle = "#a63d2b"; c.fillRect(44, 44, w - 88, h - 88);
    const diamond = (x, y, s, col) => { c.fillStyle = col; c.beginPath(); c.moveTo(x, y - s); c.lineTo(x + s * 1.3, y); c.lineTo(x, y + s); c.lineTo(x - s * 1.3, y); c.closePath(); c.fill(); };
    for (let i = 0; i < 3; i++) { const x = w / 2 + (i - 1) * 130; diamond(x, h / 2, 78, "#e9dcc0"); diamond(x, h / 2, 56, "#23395b"); diamond(x, h / 2, 30, "#d99a2b"); }
    c.fillStyle = "#e9dcc0"; for (let x = 60; x < w - 60; x += 28) { c.fillRect(x, 56, 14, 6); c.fillRect(x, h - 62, 14, 6); }
  });
}
function haloTexture(){
  return tex(256, 256, (c, w, h) => { const g = c.createRadialGradient(w / 2, h / 2, 8, w / 2, h / 2, w / 2); g.addColorStop(0, "rgba(255,255,255,1)"); g.addColorStop(0.35, "rgba(255,255,255,.45)"); g.addColorStop(1, "rgba(255,255,255,0)"); c.fillStyle = g; c.fillRect(0, 0, w, h); });
}
function flameTexture(){
  return tex(128, 256, (c, w, h) => { const g = c.createRadialGradient(w / 2, h * 0.78, 4, w / 2, h * 0.6, h * 0.62); g.addColorStop(0, "rgba(255,246,200,1)"); g.addColorStop(0.3, "rgba(255,170,50,.9)"); g.addColorStop(0.7, "rgba(230,70,20,.35)"); g.addColorStop(1, "rgba(200,40,10,0)");
    c.fillStyle = g; c.beginPath(); c.moveTo(w / 2, 6); c.bezierCurveTo(w * 0.95, h * 0.45, w * 0.9, h * 0.95, w / 2, h - 4); c.bezierCurveTo(w * 0.1, h * 0.95, w * 0.05, h * 0.45, w / 2, 6); c.fill(); });
}
function skyTexture(s){
  return tex(16, 512, (c, w, h) => { const g = c.createLinearGradient(0, 0, 0, h); g.addColorStop(0, s.top); g.addColorStop(0.30, s.top); g.addColorStop(0.455, s.mid); g.addColorStop(0.497, s.low); g.addColorStop(0.515, s.haze); g.addColorStop(1, s.haze);      /* the horizon is halfway down */ c.fillStyle = g; c.fillRect(0, 0, w, h); });
}
/* A poster: printed paper, drawn large. look "ballot" is cream with red and blue; "record" is deep green with gold. */
function posterTexture(p){
  return tex(768, 1152, (c, w, h) => {
    const ballot = p.look !== "record", ink = ballot ? "#16233f" : "#f4ead2", accent = ballot ? "#c0392b" : "#e2b34a", paper = ballot ? "#f7f0e1" : "#17352c";
    c.fillStyle = paper; c.fillRect(0, 0, w, h);
    const r = rng(ballot ? 3 : 5); for (let i = 0; i < 900; i++) { c.fillStyle = `rgba(${ballot ? "120,90,40" : "255,255,255"},${r() * 0.035})`; c.fillRect(r() * w, r() * h, 2 + r() * 3, 1 + r() * 2); }
    c.strokeStyle = accent; c.lineWidth = 10; c.strokeRect(26, 26, w - 52, h - 52); c.lineWidth = 2; c.strokeRect(44, 44, w - 88, h - 88);
    if (ballot) { c.fillStyle = "#1f3a6e"; c.fillRect(44, 44, w - 88, 150); c.fillStyle = "#fff"; for (let i = 0; i < 9; i++) star(c, 96 + i * 72, 100, 15); }
    else { c.fillStyle = accent; c.fillRect(44, 44, w - 88, 8); }
    c.fillStyle = ballot ? "#fff" : accent; c.font = "700 34px 'Trebuchet MS', 'Segoe UI', system-ui, sans-serif"; c.textAlign = "center"; c.textBaseline = "middle";
    spaced(c, p.kicker.toUpperCase(), w / 2, ballot ? 158 : 112, 5);
    /* the picture */
    if (ballot) { const y0 = 222; c.strokeStyle = ink; c.fillStyle = "#fff"; c.lineWidth = 6; c.beginPath(); c.roundRect(w / 2 - 180, y0, 360, 228, 10); c.fill(); c.stroke();
      for (let i = 0; i < 4; i++) { const yy = y0 + 39 + i * 50; c.lineWidth = 5; c.strokeStyle = ink; c.beginPath(); c.ellipse(w / 2 - 128, yy, 21, 13, 0, 0, 7); if (i === 1) { c.fillStyle = accent; c.fill(); } c.stroke(); c.fillStyle = i === 1 ? ink : "#9aa3b5"; c.fillRect(w / 2 - 88, yy - 8, i === 1 ? 236 : 180 + (i % 2) * 36, 16); } }
    else dome(c, w / 2, 452, accent);
    /* the words: the headline is made to fit above the way in, however long it runs */
    const bw = 400, bh = 84, bx = w / 2 - bw / 2, by = h - 204, top = ballot ? 548 : 562;
    c.textBaseline = "alphabetic"; let size = 80, lines = 9, lh = 0;
    const count = (text, maxW) => { let n = 1, line = ""; for (const wd of text.split(/\s+/)) { const t = line ? line + " " + wd : wd; if (c.measureText(t).width > maxW && line) { n++; line = wd; } else line = t; } return n; };
    for (; size > 44; size -= 4) { c.font = `700 ${size}px Georgia, 'Times New Roman', serif`; lh = Math.round(size * 1.08); lines = count(p.head, w - 150); c.font = "400 32px 'Trebuchet MS', 'Segoe UI', system-ui, sans-serif"; const subLines = count(p.sub, w - 190); if (top + lines * lh + 30 + subLines * 42 < by - 18) break; }
    c.fillStyle = ink; c.font = `700 ${size}px Georgia, 'Times New Roman', serif`; let y = wrap(c, p.head, w / 2, top + size * 0.82, w - 150, lh, "center") - size * 0.82;
    c.fillStyle = accent; c.fillRect(w / 2 - 60, y + 2, 120, 6);
    c.fillStyle = ink; c.globalAlpha = 0.92; c.font = "400 32px 'Trebuchet MS', 'Segoe UI', system-ui, sans-serif"; wrap(c, p.sub, w / 2, y + 54, w - 190, 42, "center"); c.globalAlpha = 1;
    /* the way in */
    c.fillStyle = accent; c.beginPath(); c.roundRect(bx, by, bw, bh, 42); c.fill();
    c.fillStyle = ballot ? "#fff" : "#17352c"; c.font = "700 40px 'Trebuchet MS', 'Segoe UI', system-ui, sans-serif"; c.textBaseline = "middle"; c.fillText(p.cta + "  ›", w / 2, by + bh / 2 + 2);
    c.fillStyle = ink; c.globalAlpha = 0.7; c.font = "400 25px 'Trebuchet MS', 'Segoe UI', system-ui, sans-serif"; spaced(c, (p.foot || "").toUpperCase(), w / 2, h - 82, 3); c.globalAlpha = 1;
  });
}
function star(c, x, y, r){ c.beginPath(); for (let i = 0; i < 10; i++) { const a = -Math.PI / 2 + i * Math.PI / 5, rr = i % 2 ? r * 0.42 : r; c.lineTo(x + Math.cos(a) * rr, y + Math.sin(a) * rr); } c.closePath(); c.fill(); }
function spaced(c, text, x, y, gap){ const ws = [...text].map(ch => c.measureText(ch).width + gap), total = ws.reduce((a, b) => a + b, 0) - gap; let xx = x - total / 2; const al = c.textAlign; c.textAlign = "left"; [...text].forEach((ch, i) => { c.fillText(ch, xx, y); xx += ws[i]; }); c.textAlign = al; }
function dome(c, x, y, col){      // a statehouse dome in gold line: steps, columns, drum, dome, lantern
  c.strokeStyle = col; c.fillStyle = col; c.lineWidth = 6; c.lineJoin = "round";
  c.fillRect(x - 230, y, 460, 12); c.fillRect(x - 200, y - 18, 400, 12);
  for (let i = 0; i < 8; i++) c.fillRect(x - 172 + i * 47, y - 118, 16, 100);
  c.fillRect(x - 196, y - 134, 392, 14); c.beginPath(); c.moveTo(x - 206, y - 134); c.lineTo(x, y - 190); c.lineTo(x + 206, y - 134); c.closePath(); c.stroke();
  c.strokeRect(x - 86, y - 246, 172, 56); for (let i = 0; i < 6; i++) c.fillRect(x - 70 + i * 26, y - 238, 8, 42);
  c.beginPath(); c.arc(x, y - 248, 92, Math.PI, 0); c.stroke(); c.beginPath(); c.moveTo(x - 92, y - 248); c.lineTo(x + 92, y - 248); c.stroke();
  c.strokeRect(x - 16, y - 372, 32, 34); c.beginPath(); c.moveTo(x, y - 372); c.lineTo(x, y - 408); c.stroke(); c.beginPath(); c.arc(x, y - 414, 7, 0, 7); c.fill();
}

/* ---------- outside: sky, sun or moon, stars, three ranges of the Rockies, meadow and trees ---------- */
function ridge(seed, z, base, height, halfW, snowline, s, far){
  const r = rng(seed), n = 340, rows = 5, pos = [], col = [], idx = [];
  const ph = [r() * 9, r() * 9, r() * 9, r() * 9], rock = new THREE.Color(s.rock), snow = new THREE.Color(s.snow), wood = new THREE.Color(s.wood), haze = new THREE.Color(s.haze);
  const mix = (a, b, t) => a.clone().lerp(b, t), tone = (cc) => cc.lerp(haze, far);
  const peaks = []; for (let i = 0, np = 8 + Math.floor(r() * 4); i < np; i++) peaks.push([0.05 + r() * 0.9, 0.42 + r() * 0.58, 0.045 + r() * 0.085]);      // pointed summits: place, height, half-width
  for (let i = 0; i <= n; i++) { const u = i / n, x = (u * 2 - 1) * halfW;
    let p = 0.15 + 0.05 * Math.sin(u * 9 + ph[0]);
    for (const [c, hh, ww] of peaks) { const d = Math.abs(u - c) / ww; if (d < 1) p = Math.max(p, hh * (1 - Math.pow(d, 0.7))); }
    p += 0.05 * (1 - Math.abs(Math.sin(u * 43 + ph[1]))) + 0.035 * (1 - Math.abs(Math.sin(u * 101 + ph[2]))) + (r() - 0.5) * 0.03;
    p = Math.max(0.1, p) * (0.7 + 0.3 * Math.sin(u * Math.PI));      // lower toward the ends of the range
    const top = height * p, line = snowline + (r() - 0.5) * 0.10;
    for (let k = 0; k < rows; k++) { const f = k / (rows - 1), y = base + top * f, hgt = (top * f) / height;
      let cc = f < 0.25 ? mix(wood, rock, f / 0.25) : hgt > line ? mix(rock, snow, Math.min(1, (hgt - line) / 0.10 + 0.25)) : rock.clone();
      if (k === 0) cc = wood.clone(); pos.push(x, k === 0 ? base - 30 : y, z + (r() - 0.5) * 2); tone(cc); col.push(cc.r, cc.g, cc.b); }
    if (i < n) for (let k = 0; k < rows - 1; k++) { const a = i * rows + k, b = a + rows; idx.push(a, b, a + 1, b, b + 1, a + 1); } }
  const g = new THREE.BufferGeometry(); g.setAttribute("position", new THREE.Float32BufferAttribute(pos, 3)); g.setAttribute("color", new THREE.Float32BufferAttribute(col, 3)); g.setIndex(idx);
  return new THREE.Mesh(g, new THREE.MeshBasicMaterial({vertexColors: true, side: THREE.DoubleSide, fog: false}));
}
function outside(scene, s, land){
  const g = new THREE.Group(); scene.add(g);
  const sky = new THREE.Mesh(new THREE.SphereGeometry(480, 24, 16), new THREE.MeshBasicMaterial({map: skyTexture(s), side: THREE.BackSide, fog: false})); g.add(sky);
  const halo = haloTexture(), sunPos = new THREE.Vector3(s.sun[0] * 300, 4 + s.sun[1] * 150, -420);
  const disc = new THREE.Mesh(new THREE.CircleGeometry(s.stars === 1 ? 9 : 13, 40), new THREE.MeshBasicMaterial({color: s.disc, fog: false})); disc.position.copy(sunPos); g.add(disc);
  const glow = new THREE.Mesh(new THREE.PlaneGeometry(190, 190), new THREE.MeshBasicMaterial({map: halo, color: s.disc, transparent: true, opacity: s.stars === 1 ? 0.35 : 0.8, blending: THREE.AdditiveBlending, depthWrite: false, fog: false})); glow.position.copy(sunPos).z += 2; g.add(glow);
  if (s.stars > 0) { const r = rng(99), p = []; for (let i = 0; i < 700; i++) { const a = r() * Math.PI - Math.PI, e = 0.06 + r() * 1.2; p.push(Math.cos(a) * Math.cos(e) * 460, Math.sin(e) * 460, Math.sin(a) * Math.cos(e) * 460); }
    const sg = new THREE.BufferGeometry(); sg.setAttribute("position", new THREE.Float32BufferAttribute(p, 3));
    g.add(new THREE.Points(sg, new THREE.PointsMaterial({color: "#ffffff", size: 1.7, sizeAttenuation: false, transparent: true, opacity: 0.9 * s.stars, fog: false}))); }
  const r = rng(41);      // a few clouds
  for (let i = 0; i < 7; i++) { const m = new THREE.Mesh(new THREE.PlaneGeometry(90 + r() * 110, 16 + r() * 16), new THREE.MeshBasicMaterial({map: halo, color: s.cloud, transparent: true, opacity: s.stars === 1 ? 0.25 : 0.55, depthWrite: false, fog: false}));
    m.position.set((r() * 2 - 1) * 330, 70 + r() * 90, -400 + r() * 20); g.add(m); }
  const GY = -2.6;      // the cabin stands on a rise: the meadow lies below the floor, so the valley opens out under the window
  g.add(ridge(1, -330, GY - 6, 92, 520, land.snowline - 0.10, s, 0.30));      // the far range, palest, the most snow
  g.add(ridge(2, -250, GY - 6, 58, 430, land.snowline, s, 0.14));
  g.add(ridge(3, -170, GY - 5, 22, 330, land.snowline + 0.5, s, 0.04));       // the near, wooded foothills: no snow but in winter
  const ground = new THREE.Mesh(new THREE.PlaneGeometry(700, 260), new THREE.MeshLambertMaterial({color: land.ground})); ground.rotation.x = -Math.PI / 2; ground.position.set(0, GY - 0.55, -133); g.add(ground);
  /* pines and aspens, drawn as instances; a clear way down the middle keeps the mountains in the window */
  const tr = rng(5), M = new THREE.Matrix4(), Q = new THREE.Quaternion(), V = new THREE.Vector3(), S = new THREE.Vector3();
  const spots = []; for (let i = 0; i < 190; i++) { const z = -10 - Math.pow(tr(), 1.4) * 125, x = (tr() * 2 - 1) * (30 + -z * 0.95); if (Math.abs(x) < 8 + -z * 0.24) continue; spots.push([x, z, 0.75 + tr() * 0.9, tr() < 0.3]); }
  const pines = spots.filter(p => !p[3]), aspens = spots.filter(p => p[3] && land.aspen);
  const trunkM = new THREE.MeshLambertMaterial({color: "#4a3323"}), pineM = new THREE.MeshLambertMaterial({color: land.pine}), tipM = new THREE.MeshLambertMaterial({color: land.pineTip});
  const cone = new THREE.ConeGeometry(1.5, 3.4, 9), inst = (geo, mat, list, f) => { const im = new THREE.InstancedMesh(geo, mat, list.length); list.forEach((p, i) => { f(p); M.compose(V, Q, S); im.setMatrixAt(i, M); }); g.add(im); return im; };
  inst(new THREE.CylinderGeometry(0.16, 0.22, 1.4, 6), trunkM, pines, p => { V.set(p[0], GY + 0.15, p[1]); S.set(p[2], p[2], p[2]); });
  inst(cone, pineM, pines, p => { V.set(p[0], GY + 2.4 * p[2], p[1]); S.set(p[2], p[2], p[2]); });
  inst(cone, tipM, pines, p => { V.set(p[0], GY + 4.3 * p[2], p[1]); S.set(p[2] * 0.68, p[2] * 0.8, p[2] * 0.68); });
  if (aspens.length) { inst(new THREE.CylinderGeometry(0.07, 0.1, 3.4, 6), new THREE.MeshLambertMaterial({color: "#e8e4d8"}), aspens, p => { V.set(p[0], GY + 1.1, p[1]); S.set(p[2], p[2], p[2]); });
    inst(new THREE.IcosahedronGeometry(1.1, 1), new THREE.MeshLambertMaterial({color: land.aspen, emissive: land.aspen, emissiveIntensity: 0.12, flatShading: true}), aspens, p => { V.set(p[0], GY + 3.4 * p[2], p[1]); S.set(p[2], p[2] * 1.3, p[2]); }); }
  return g;
}

/* ---------- the room and its furniture ---------- */
function room(scene, s, opts){
  const g = new THREE.Group(); scene.add(g);
  const logs = logsTexture(), planks = planksTexture(), stone = stoneTexture(), halo = haloTexture();
  const logM = std({map: logs}), darkWood = std({color: "#5a3a22"}), midWood = std({color: "#8a5c36"});
  planks.repeat.set(4, 3.2); const floor = new THREE.Mesh(new THREE.PlaneGeometry(W, D), std({map: planks, roughness: 0.8})); floor.rotation.x = -Math.PI / 2; g.add(floor);
  const ceilT = planksTexture(); ceilT.repeat.set(5, 4); const ceil = new THREE.Mesh(new THREE.PlaneGeometry(W, D), std({map: ceilT, color: "#9a7a58"})); ceil.rotation.x = Math.PI / 2; ceil.position.y = H; g.add(ceil);
  for (let i = 0; i < 4; i++) box(W, 0.2, 0.24, darkWood, 0, H - 0.1, -HZ + 0.9 + i * 1.6, g);
  /* walls: the far wall is built around the window */
  const wx = WIN.x1 - WIN.x0;
  wall(HX + WIN.x0, H, logM, (-HX + WIN.x0) / 2, H / 2, -HZ, 0, g); wall(HX - WIN.x1, H, logM, (HX + WIN.x1) / 2, H / 2, -HZ, 0, g);
  wall(wx, WIN.y0, logM, 0, WIN.y0 / 2, -HZ, 0, g); wall(wx, H - WIN.y1, logM, 0, (H + WIN.y1) / 2, -HZ, 0, g);
  wall(D, H, logM, -HX, H / 2, 0, Math.PI / 2, g); wall(D, H, logM, HX, H / 2, 0, -Math.PI / 2, g); wall(W, H, logM, 0, H / 2, HZ, Math.PI, g);
  /* the window: frame, mullions, glass, a seat beneath it */
  const wy = (WIN.y0 + WIN.y1) / 2, wh = WIN.y1 - WIN.y0;
  box(wx + 0.24, 0.12, 0.22, darkWood, 0, WIN.y1 + 0.06, -HZ, g); box(wx + 0.36, 0.1, 0.34, darkWood, 0, WIN.y0 - 0.05, -HZ + 0.05, g);
  box(0.12, wh, 0.22, darkWood, WIN.x0 - 0.06, wy, -HZ, g); box(0.12, wh, 0.22, darkWood, WIN.x1 + 0.06, wy, -HZ, g);
  box(0.07, wh, 0.1, darkWood, -0.7, wy, -HZ, g); box(0.07, wh, 0.1, darkWood, 0.7, wy, -HZ, g); box(wx, 0.07, 0.1, darkWood, 0, WIN.y0 + wh * 0.66, -HZ, g);
  const glass = new THREE.Mesh(new THREE.PlaneGeometry(wx, wh), new THREE.MeshBasicMaterial({color: "#9fc4e8", transparent: true, opacity: s.glass, depthWrite: false})); glass.position.set(0, wy, -HZ - 0.02); g.add(glass);
  box(wx - 0.1, 0.42, 0.52, midWood, 0, 0.21, -HZ + 0.27, g); box(wx - 0.2, 0.1, 0.48, std({color: "#7b2f2a", roughness: 1}), 0, 0.47, -HZ + 0.27, g);
  box(0.42, 0.16, 0.4, std({color: "#d9c79a", roughness: 1}), -1.5, 0.6, -HZ + 0.28, g).rotation.z = 0.5; box(0.42, 0.16, 0.4, std({color: "#2f4f6b", roughness: 1}), 1.45, 0.6, -HZ + 0.28, g).rotation.z = -0.45;
  /* the fireplace on the right-hand wall */
  stone.repeat.set(1.6, 2.4); const stoneM = std({map: stone, roughness: 1}), fz = 0.6;
  box(0.62, H, 2.0, stoneM, HX - 0.31, H / 2, fz, g); box(0.5, 0.14, 2.5, stoneM, HX - 0.72, 0.07, fz, g);
  box(0.3, 0.86, 1.06, new THREE.MeshBasicMaterial({color: "#0c0706"}), HX - 0.5, 0.57, fz, g); box(0.5, 0.14, 2.2, darkWood, HX - 0.52, 1.36, fz, g);
  const flameT = flameTexture(), flames = [];
  for (let i = 0; i < 4; i++) { const f = new THREE.Mesh(new THREE.PlaneGeometry(0.42, 0.62), new THREE.MeshBasicMaterial({map: flameT, transparent: true, blending: THREE.AdditiveBlending, depthWrite: false, side: THREE.DoubleSide}));
    f.position.set(HX - 0.72 + i * 0.01, 0.46, fz - 0.27 + i * 0.18); f.rotation.y = -Math.PI / 2; g.add(f); flames.push(f); }
  for (let i = 0; i < 3; i++) { const l = cyl(0.07, 0.07, 0.7, std({color: "#2a1a10"}), HX - 0.7, 0.2 + (i === 2 ? 0.1 : 0), fz - 0.16 + i * 0.16, g, 8); l.rotation.x = Math.PI / 2; l.rotation.z = (i - 1) * 0.3; }
  const ember = box(0.3, 0.05, 0.6, new THREE.MeshBasicMaterial({color: "#ff6a1a"}), HX - 0.7, 0.16, fz, g);
  const fire = new THREE.PointLight("#ff8a3a", s.fire, 11, 1.7); fire.position.set(HX - 1.1, 0.7, fz); g.add(fire);
  for (let i = 0; i < 9; i++) { const l = cyl(0.09, 0.09, 0.5, std({color: i % 2 ? "#7a5232" : "#8d623c"}), HX - 0.3, 0.1 + Math.floor(i / 3) * 0.17, -1.55 + (i % 3) * 0.19 + (Math.floor(i / 3) % 2) * 0.09, g, 8); l.rotation.z = Math.PI / 2; }
  box(0.22, 0.3, 0.16, std({color: "#7a5a3a"}), HX - 0.5, 1.58, fz - 0.6, g); cyl(0.05, 0.07, 0.24, std({color: "#3a5a4a"}), HX - 0.5, 1.55, fz + 0.7, g); cyl(0.09, 0.09, 0.02, std({color: "#c9a24a", metalness: 0.5, roughness: 0.4}), HX - 0.5, 1.64, fz, g).rotation.z = Math.PI / 2;
  /* rug, two armchairs, a side table with a lamp and a mug */
  const rug = new THREE.Mesh(new THREE.PlaneGeometry(3.1, 2.2), std({map: rugTexture(), roughness: 1})); rug.rotation.x = -Math.PI / 2; rug.position.set(1.95, 0.012, fz); g.add(rug);
  const chair = (x, z, ry, col) => { const c = new THREE.Group(), fab = std({color: col, roughness: 1}), legs = std({color: "#3d2616"});
    box(0.74, 0.2, 0.72, fab, 0, 0.4, 0, c); box(0.62, 0.1, 0.6, std({color: "#d8c9a6", roughness: 1}), 0, 0.53, 0.02, c); box(0.74, 0.74, 0.16, fab, 0, 0.78, -0.3, c);
    box(0.14, 0.3, 0.72, fab, -0.36, 0.62, 0, c); box(0.14, 0.3, 0.72, fab, 0.36, 0.62, 0, c);
    [[-0.3, -0.28], [0.3, -0.28], [-0.3, 0.28], [0.3, 0.28]].forEach(p => cyl(0.03, 0.025, 0.3, legs, p[0], 0.15, p[1], c, 8));
    c.position.set(x, 0, z); c.rotation.y = ry; g.add(c); return c; };
  chair(1.5, fz - 1.15, Math.PI / 2 - 0.35, "#2f5a44"); chair(1.5, fz + 1.15, Math.PI / 2 + 0.35, "#8a3b2a");      // both turned toward the fire
  box(0.5, 0.04, 0.34, std({color: "#c9b38a", roughness: 1}), 1.63, 0.58, fz + 1.36, g).rotation.y = 0.4;       // a blanket over an arm
  const tx = 1.15;      // the side table between the chairs, with the lamp and a mug
  cyl(0.27, 0.27, 0.04, midWood, tx, 0.58, fz, g, 24); cyl(0.04, 0.05, 0.56, darkWood, tx, 0.29, fz, g); cyl(0.17, 0.2, 0.03, darkWood, tx, 0.015, fz, g, 20);
  cyl(0.06, 0.08, 0.05, std({color: "#3a2a1c"}), tx - 0.05, 0.625, fz - 0.05, g); cyl(0.015, 0.015, 0.3, std({color: "#b08a4a", metalness: 0.6, roughness: 0.4}), tx - 0.05, 0.78, fz - 0.05, g, 8);
  const shade = cyl(0.09, 0.16, 0.2, new THREE.MeshBasicMaterial({color: s.lamp ? "#ffe2ad" : "#d9cdb4"}), tx - 0.05, 0.98, fz - 0.05, g, 20);
  const lamp = new THREE.PointLight("#ffd9a0", s.lamp, 8, 1.8); lamp.position.set(tx - 0.05, 1.02, fz - 0.05); g.add(lamp);
  cyl(0.04, 0.035, 0.08, std({color: "#e9e2d2", roughness: 0.5}), tx + 0.11, 0.64, fz + 0.1, g);
  /* the bookshelf on the left-hand wall */
  const bx = -HX + 0.2, bz = 0.75, bw = 1.7, bh = 2.1;
  box(0.36, bh, 0.05, darkWood, bx, bh / 2, bz - bw / 2, g); box(0.36, bh, 0.05, darkWood, bx, bh / 2, bz + bw / 2, g); box(0.03, bh, bw, darkWood, bx - 0.16, bh / 2, bz, g);
  const books = [], br = rng(17), pal = ["#7a2e22", "#23395b", "#2f5a44", "#b08a3a", "#5a3a5a", "#8a5a2a", "#3a3a3a", "#c9b38a", "#234a5a"];
  for (let sI = 0; sI < 6; sI++) { const y = 0.03 + sI * (bh - 0.06) / 5; box(0.36, 0.04, bw, darkWood, bx, y, bz, g); if (sI === 5) break;
    let z = bz - bw / 2 + 0.06; while (z < bz + bw / 2 - 0.1) { const t = 0.03 + br() * 0.045, hgt = 0.2 + br() * 0.13; if (br() < 0.1) { z += 0.12 + br() * 0.1; continue; } books.push([bx + 0.02 + br() * 0.03, y + 0.02 + hgt / 2, z + t / 2, 0.22 + br() * 0.05, hgt, t, pal[Math.floor(br() * pal.length)]]); z += t + 0.004; } }
  const bm = new THREE.InstancedMesh(new THREE.BoxGeometry(1, 1, 1), std({roughness: 0.8}), books.length), M = new THREE.Matrix4(), C = new THREE.Color();
  books.forEach((b, i) => { M.makeScale(b[3], b[4], b[5]); M.setPosition(b[0], b[1], b[2]); bm.setMatrixAt(i, M); bm.setColorAt(i, C.set(b[6])); }); g.add(bm);
  /* a lantern from the middle beam, and the cabin door behind the visitor */
  const lx = -2.3, lz = 0.9;      // off to the left, over the open floor, so it does not hang in front of the window
  cyl(0.006, 0.006, 0.3, std({color: "#222"}), lx, H - 0.35, lz, g, 6); box(0.11, 0.15, 0.11, new THREE.MeshBasicMaterial({color: s.lantern ? "#ffd89a" : "#cfc6b0"}), lx, H - 0.58, lz, g); box(0.15, 0.025, 0.15, std({color: "#222"}), lx, H - 0.495, lz, g);
  const lantern = new THREE.PointLight("#ffd08a", s.lantern, 9, 1.8); lantern.position.set(lx, H - 0.66, lz); g.add(lantern);
  box(0.96, 2.05, 0.08, std({color: "#6a4526"}), -1.6, 1.025, HZ - 0.03, g); box(1.12, 0.1, 0.12, darkWood, -1.6, 2.1, HZ - 0.04, g); box(0.08, 2.1, 0.12, darkWood, -2.12, 1.05, HZ - 0.04, g); box(0.08, 2.1, 0.12, darkWood, -1.08, 1.05, HZ - 0.04, g);
  cyl(0.03, 0.03, 0.06, std({color: "#c9a24a", metalness: 0.6, roughness: 0.4}), -1.25, 1.0, HZ - 0.09, g).rotation.x = Math.PI / 2;
  /* the two posters, either side of the window: paper that needs no light, a frame, a halo, and a light of their own */
  const posters = (opts.posters || []).slice(0, 2).map((p, i) => { const pg = new THREE.Group(), x = (i ? 1 : -1) * 3.13, pw = 1.14, ph = 1.71, tint = p.look === "record" ? "#ffd27a" : "#9cc4ff";
    const paper = new THREE.Mesh(new THREE.PlaneGeometry(pw, ph), new THREE.MeshBasicMaterial({map: posterTexture(p), toneMapped: false})); paper.position.z = 0.05; pg.add(paper);
    const fr = std({color: "#3a2414", emissive: tint, emissiveIntensity: 0.25});
    box(pw + 0.14, 0.07, 0.06, fr, 0, ph / 2 + 0.035, 0.03, pg); box(pw + 0.14, 0.07, 0.06, fr, 0, -ph / 2 - 0.035, 0.03, pg); box(0.07, ph, 0.06, fr, -pw / 2 - 0.035, 0, 0.03, pg); box(0.07, ph, 0.06, fr, pw / 2 + 0.035, 0, 0.03, pg);
    const glow = new THREE.Mesh(new THREE.PlaneGeometry(pw * 2.3, ph * 1.8), new THREE.MeshBasicMaterial({map: halo, color: tint, transparent: true, opacity: 0.5, blending: THREE.AdditiveBlending, depthWrite: false})); glow.position.z = 0.012; pg.add(glow);
    const light = new THREE.PointLight(tint, s.poster, 5, 1.6); light.position.set(0, 0.2, 0.7); pg.add(light);
    pg.position.set(x, 1.58, -HZ + 0.01); g.add(pg);
    return {group: pg, paper, glow, light, frame: fr, url: p.url, x, stand: new THREE.Vector3(x * 0.86, EYE, -HZ + 1.75), heat: 0}; });
  return {group: g, flames, fire, ember, lamp, lantern, shade, posters, floor};
}
/* where a visitor cannot stand: the window seat, the fireplace and its hearth, the chairs and table, the bookshelf */
const BLOCKS = [[-2.15, 2.15, -HZ, -HZ + 0.56], [HX - 1.0, HX, -0.7, 1.9], [HX - 0.5, HX, -1.8, -0.9], [1.0, 1.95, -1.0, -0.12], [1.0, 1.95, 1.32, 2.2], [0.85, 1.45, 0.3, 0.9], [-HX, -HX + 0.42, -0.15, 1.65]];
function free(x, z){
  if (x < -HX + RADIUS || x > HX - RADIUS || z < -HZ + RADIUS || z > HZ - RADIUS) return false;
  return !BLOCKS.some(b => x > b[0] - RADIUS && x < b[1] + RADIUS && z > b[2] - RADIUS && z < b[3] + RADIUS);
}

/* ---------- the room, running ---------- */
export function start(canvas, opts = {}){
  const calm = !!opts.calm;
  let renderer;
  try { renderer = new THREE.WebGLRenderer({canvas, antialias: true, powerPreference: "high-performance"}); } catch (e) { return null; }
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  const scene = new THREE.Scene(), camera = new THREE.PerspectiveCamera(62, 1, 0.05, 1200);
  camera.rotation.order = "YXZ";
  const hemi = new THREE.HemisphereLight(), sun = new THREE.DirectionalLight(); scene.add(hemi, sun);
  let R = null, OUT = null, S = null;
  const me = {x: -0.5, z: 2.35, yaw: -0.09, pitch: 0.0, bob: 0};      // just inside the door, facing the window and both posters
  function build(when, season){
    if (R) { scene.remove(R.group); scene.remove(OUT); }
    S = SKY[when] || SKY[whenNow()]; const land = LAND[season] || LAND[seasonNow()];
    renderer.toneMappingExposure = S.expo; hemi.intensity = S.hemi[0]; hemi.color.set(S.hemi[1]); hemi.groundColor.set(S.hemi[2]); sun.intensity = S.dir[0]; sun.color.set(S.dir[1]); sun.position.set(...S.dir[2]);
    OUT = outside(scene, S, land); R = room(scene, S, opts);
  }
  build(opts.when || whenNow(), opts.season || seasonNow());

  function size(w, h){
    const ratio = Math.min(devicePixelRatio || 1, 2); w = w || canvas.clientWidth || 960; h = h || canvas.clientHeight || 600;
    renderer.setPixelRatio(ratio); renderer.setSize(w, h, false); camera.aspect = w / h;
    const hf = 84 * Math.PI / 180;      // keep both posters in view on a tall, narrow screen
    camera.fov = Math.max(58, Math.min(86, 2 * Math.atan(Math.tan(hf / 2) / camera.aspect) * 180 / Math.PI)); camera.updateProjectionMatrix();
  }
  size();

  /* ---- moving and looking ---- */
  const keys = new Set(), MOVE = new Set(["w", "a", "s", "d", "arrowup", "arrowdown", "arrowleft", "arrowright"]);
  let walkTo = null, going = null, moved = false, hover = -1, raf = 0, last = 0, clock = 0, dead = false;
  const told = () => { if (!moved) { moved = true; opts.onMove && opts.onMove(); } };
  const onKey = e => { const k = e.key.toLowerCase(); if (!MOVE.has(k) || e.ctrlKey || e.metaKey || e.altKey) return; const t = e.target; if (t && t !== document.body && t !== canvas && /^(INPUT|TEXTAREA|SELECT)$/.test(t.tagName)) return;
    if (e.type === "keydown") { keys.add(k); walkTo = null; told(); kick(); e.preventDefault(); } else keys.delete(k); };
  addEventListener("keydown", onKey); addEventListener("keyup", onKey); const onBlur = () => keys.clear(); addEventListener("blur", onBlur);

  const ray = new THREE.Raycaster(), ndc = new THREE.Vector2();
  function pick(ev){
    const b = canvas.getBoundingClientRect(); ndc.set(((ev.clientX - b.left) / b.width) * 2 - 1, -((ev.clientY - b.top) / b.height) * 2 + 1); ray.setFromCamera(ndc, camera);
    const hit = ray.intersectObjects(R.posters.map(p => p.paper), false)[0]; if (hit) return {poster: R.posters.findIndex(p => p.paper === hit.object)};
    const f = ray.intersectObject(R.floor, false)[0]; return f ? {floor: f.point} : {};
  }
  let down = null;      // no pointer capture: the listeners for the drag sit on the window (a captured pointer once made the door's cards unclickable)
  const onDown = ev => { if (going) return; down = {x: ev.clientX, y: ev.clientY, drag: false, id: ev.pointerId}; };
  const onMoveP = ev => {
    if (down && ev.pointerId === down.id) { const dx = ev.clientX - down.x, dy = ev.clientY - down.y;
      if (!down.drag && Math.hypot(dx, dy) > 6) down.drag = true;
      if (down.drag && ev.pointerType !== "touch") { me.yaw += (ev.movementX || 0) * 0.0042; me.pitch = Math.max(-0.6, Math.min(0.5, me.pitch + (ev.movementY || 0) * 0.0032)); told(); kick(); }
      return; }
    if (ev.target !== canvas || going) return;
    const p = pick(ev), h = p.poster != null ? p.poster : -1; if (h !== hover) { hover = h; canvas.style.cursor = h >= 0 ? "pointer" : "grab"; opts.onHover && opts.onHover(h); kick(); }
  };
  const onUp = ev => { if (!down || ev.pointerId !== down.id) return; const d = down; down = null; if (d.drag || going || ev.target !== canvas) return;
    const p = pick(ev); if (p.poster != null) go(p.poster); else if (p.floor) { walkTo = nearestFree(p.floor.x, p.floor.z); told(); kick(); } };
  canvas.addEventListener("pointerdown", onDown); addEventListener("pointermove", onMoveP); addEventListener("pointerup", onUp); addEventListener("pointercancel", onUp);
  canvas.style.touchAction = "none"; canvas.style.cursor = "grab";
  let lastTouch = null;      // a finger gives no movementX in some browsers: work the turn out from positions
  const onTouch = ev => { const t = ev.touches[0]; if (!t) { lastTouch = null; return; } if (lastTouch && down && down.drag) { me.yaw += (t.clientX - lastTouch.x) * 0.0046; me.pitch = Math.max(-0.6, Math.min(0.5, me.pitch + (t.clientY - lastTouch.y) * 0.0034)); kick(); } lastTouch = {x: t.clientX, y: t.clientY}; };
  canvas.addEventListener("touchmove", onTouch, {passive: true}); canvas.addEventListener("touchend", () => { lastTouch = null; }, {passive: true});

  function nearestFree(x, z){ x = Math.max(-HX + RADIUS, Math.min(HX - RADIUS, x)); z = Math.max(-HZ + RADIUS, Math.min(HZ - RADIUS, z));
    if (free(x, z)) return {x, z}; for (let r = 0.2; r < 2.4; r += 0.2) for (let a = 0; a < 12; a++) { const nx = x + Math.cos(a * Math.PI / 6) * r, nz = z + Math.sin(a * Math.PI / 6) * r; if (free(nx, nz)) return {x: nx, z: nz}; } return {x: me.x, z: me.z}; }
  const yawTo = (x, z) => Math.atan2(-(x - me.x), -(z - me.z));
  const turn = (to, k) => { let d = to - me.yaw; d = Math.atan2(Math.sin(d), Math.cos(d)); me.yaw += d * k; return Math.abs(d); };

  function go(i){      // walk up to a poster, then leave through it
    const p = R.posters[i]; if (!p || going) return; told();
    if (calm) { opts.onLeave && opts.onLeave(p.url, i); return; }
    going = {i, t: 0, from: {x: me.x, z: me.z, yaw: me.yaw, pitch: me.pitch}, left: false}; walkTo = null; kick();
  }
  function look(i){ const p = R.posters[i]; if (!p || going) return; me.yaw = yawTo(p.x, -HZ); me.pitch = 0; kick(); }

  function step(dt){
    clock += dt;
    if (going) { const p = R.posters[going.i], g = going; g.t += dt / 1.5; const e = g.t >= 1 ? 1 : 1 - Math.pow(1 - g.t, 3);
      me.x = g.from.x + (p.stand.x - g.from.x) * e; me.z = g.from.z + (p.stand.z - g.from.z) * e; const want = Math.atan2(-(p.x - me.x), -(-HZ - me.z)); let d = want - g.from.yaw; d = Math.atan2(Math.sin(d), Math.cos(d)); me.yaw = g.from.yaw + d * e; me.pitch = g.from.pitch * (1 - e);
      p.heat = Math.min(1, p.heat + dt * 2);
      if (g.t >= 1 && !g.left) { g.left = true; opts.onLeave && opts.onLeave(p.url, g.i); }
      return true; }
    let fwd = 0, side = 0, rot = 0;
    if (keys.has("w") || keys.has("arrowup")) fwd += 1; if (keys.has("s") || keys.has("arrowdown")) fwd -= 1;
    if (keys.has("a")) side -= 1; if (keys.has("d")) side += 1; if (keys.has("arrowleft")) rot += 1; if (keys.has("arrowright")) rot -= 1;
    me.yaw += rot * 1.9 * dt;
    let vx = 0, vz = 0, busy = !!(fwd || side || rot);
    if (fwd || side) { const s = Math.sin(me.yaw), c = Math.cos(me.yaw), n = Math.hypot(fwd, side) || 1; vx = (-s * fwd + c * side) / n; vz = (-c * fwd - s * side) / n; }
    else if (walkTo) { const dx = walkTo.x - me.x, dz = walkTo.z - me.z, dist = Math.hypot(dx, dz); if (dist < 0.06) walkTo = null; else { vx = dx / dist; vz = dz / dist; turn(Math.atan2(-vx, -vz), Math.min(1, dt * 3)); busy = true; } }
    if (vx || vz) { const sp = 2.3 * dt, nx = me.x + vx * sp, nz = me.z + vz * sp; let went = false;
      if (free(nx, me.z)) { me.x = nx; went = true; } if (free(me.x, nz)) { me.z = nz; went = true; }
      if (went) me.bob += dt * 9; else walkTo = null; }
    R.posters.forEach((p, i) => { const want = i === hover ? 1 : 0; if (p.heat !== want) { p.heat += Math.sign(want - p.heat) * Math.min(Math.abs(want - p.heat), dt * 4); busy = true; } });
    return busy;
  }
  function draw(){
    const f = calm ? 0 : 1, t = clock;
    camera.position.set(me.x, EYE + (calm ? 0 : Math.sin(me.bob) * 0.022), me.z); camera.rotation.set(me.pitch, me.yaw, 0);
    const fl = 0.86 + f * (0.09 * Math.sin(t * 11.3) + 0.06 * Math.sin(t * 23.1 + 1.3) + 0.05 * Math.sin(t * 5.7));
    R.fire.intensity = S.fire * fl; R.ember.material.color.setScalar(1).multiply(new THREE.Color("#ff6a1a")).multiplyScalar(0.8 + 0.2 * fl);
    R.flames.forEach((m, i) => { const k = 0.85 + f * 0.22 * Math.sin(t * (7 + i * 2.3) + i * 1.7); m.scale.set(0.9 + f * 0.12 * Math.sin(t * 9 + i), k * (S.fire > 8 ? 1 : 0.6), 1); m.position.y = 0.2 + 0.31 * m.scale.y; m.material.opacity = 0.75 + 0.2 * Math.sin(t * 13 + i * 2); });
    R.posters.forEach((p, i) => { const pulse = 0.5 + 0.5 * Math.sin(t * 1.7 + i * Math.PI) * f, k = 0.62 + 0.38 * pulse + p.heat * 0.9;
      p.glow.material.opacity = Math.min(1, 0.42 + 0.34 * k); p.glow.scale.setScalar(1 + 0.06 * pulse + 0.1 * p.heat); p.light.intensity = S.poster * k; p.frame.emissiveIntensity = 0.45 + 0.75 * k; p.group.scale.setScalar(1 + 0.025 * p.heat); });
    renderer.render(scene, camera);
  }
  function frame(now){
    raf = 0; if (dead) return; const dt = Math.min(0.05, last ? (now - last) / 1000 : 0.016); last = now;
    const busy = step(dt); draw();
    if (!calm || busy || keys.size) kick(); else last = 0;      // with motion off the room is drawn only when something changes
  }
  function kick(){ if (!raf && !dead && !document.hidden) raf = requestAnimationFrame(frame); }
  const onVis = () => { last = 0; kick(); }, onSize = () => { size(); if (calm) draw(); kick(); };
  document.addEventListener("visibilitychange", onVis); addEventListener("resize", onSize);
  draw(); kick();

  return {
    go, look,
    setWhen(when, season){ build(when, season || opts.season || seasonNow()); draw(); kick(); },
    /* one frame as a picture: view = {x, z, yaw, pitch, t} places the visitor and the moment */
    still(w = 960, h = 600, view = {}){ const keep = Object.assign({}, me), kc = clock; Object.assign(me, view); if (view.t != null) clock = view.t;
      renderer.setPixelRatio(1); renderer.setSize(w, h, false); camera.aspect = w / h; camera.updateProjectionMatrix(); draw(); const url = canvas.toDataURL("image/jpeg", 0.82);
      Object.assign(me, keep); clock = kc; size(); draw(); return url; },
    dispose(){ dead = true; cancelAnimationFrame(raf); removeEventListener("keydown", onKey); removeEventListener("keyup", onKey); removeEventListener("blur", onBlur); removeEventListener("pointermove", onMoveP); removeEventListener("pointerup", onUp); removeEventListener("pointercancel", onUp); removeEventListener("resize", onSize); document.removeEventListener("visibilitychange", onVis); renderer.dispose(); },
  };
}
