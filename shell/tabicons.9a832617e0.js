/* The Civic Archive: the live 3D icons on the rail of tabs of a member's page (John, 2026-10-09).
   Seven small desk objects in the site's three materials (brushed brass, verdigris, parchment, with ink), sculpted in code
   and lit like a product shot: a nameplate, three sheets under a clip, a gauge, a quill and inkwell, a stack of coins, a
   ballot box and an open book. One renderer draws them all into one transparent canvas laid over the rail, each aligned to
   its own pocket; they turn slowly, lean toward the pointer, and lift and glow when chosen. With motion off they are drawn
   once, still. Where WebGL is missing, mount() returns null and the page keeps its plain icons.
   The contract every builder keeps:
     mount(host, items, {still}) -> controller | null     items: [{id, slot}], slot the element inside each tab where the icon sits
     controller: select(id), hover(id|null), focus(id|null), setStill(bool), setItems(items), destroy()
   three.js is the site's own copy (vendor/, MIT), one folder up from this file; nothing is fetched from another server.
   build_shell.py copies this file into shell/ under a hashed name and writes shell/tabicons.js beside it, which imports that
   name, so a page only ever names shell/tabicons.js. */

const D = document, H = D.documentElement, TAU = Math.PI * 2, rad = d => d * Math.PI / 180;
const clamp = (v, lo, hi) => Math.min(hi, Math.max(lo, v));
const mq = q => { try { return matchMedia(q); } catch (e) { return {matches: false, addEventListener() {}, removeEventListener() {}}; } };
/* the two lightings: the pages' own brass, verdigris and parchment, a touch brighter on a dark page */
const THEME = {
  light: {brass: 0xC8963A, brassR: .27, verd: 0x2F6B5E, well: 0x255A4E, parch: 0xE8DBBC, env: .9, exposure: 1.0, shadow: .28, glow: .45, key: 2.4, rim: 1.2, hemi: .3},
  dark: {brass: 0xC9944A, brassR: .24, verd: 0x3C7F70, well: 0x2F6B5E, parch: 0xE6DCC4, env: .6, exposure: .85, shadow: .34, glow: .55, key: 2.0, rim: 2.0, hemi: .5}
};
const POSE = {yaw: 28, pitch: 14};      /* the rest view, three-quarter and a little from above; the still frame too */
const PITCH = {wiki: 8};      /* an object seen more from above than the rest: the open book, so its cover's edge shows */
const LIFT = {hover: .06, selected: .09}, SCALE_SEL = 1.06, DIAM = 1.8, BOX = 1.5, RADIUS = 1.05;      /* lifts as a share of the object's size; the drawn box as a multiple of the pocket; the sphere an object is fitted into */
const K = {office: 1.08, committees: 1.0, howvotes: 1.0, work: 1.0, money: 1.04, votes: 1.0, wiki: 1.06};      /* how much of its sphere each object fills */
/* the Calm setting of the site's Access page (no motion), kept in the same stored object as the rest of the reader's choices */
function calmNow() {
  if (H.getAttribute("data-calm") === "on") return true;
  try { const s = JSON.parse(localStorage.getItem("tca.a11y.v1") || "null"); return !!s && typeof s === "object" && s.calm === "on"; } catch (e) { return false; }
}

let libP = null;
function lib() {      /* three.js and the room it is lit by, fetched once, only when a member page opens */
  if (!libP) libP = (async () => {
    const THREE = await import(new URL("../vendor/three.module.min.js", import.meta.url).href);
    let Room = null;
    try { Room = (await import(new URL("../vendor/jsm/environments/RoomEnvironment.js", import.meta.url).href)).RoomEnvironment; } catch (e) { Room = null; }
    return {THREE, Room};
  })().catch(e => { libP = null; throw e; });
  return libP;
}
function isDark() {
  const t = H.getAttribute("data-theme");
  if (t === "dark" || t === "light") return t === "dark";
  if (H.getAttribute("data-contrast") === "dark") return true;
  return mq("(prefers-color-scheme: dark)").matches;
}

/* ---------- a spring: stiffness 120, damping 14, settling in about half a second without a bounce ---------- */
class Spring {
  constructor(v, k = 120, c = 14) { this.x = this.t = v; this.v = 0; this.k = k; this.c = c; }
  step(dt) {
    for (let n = Math.ceil(dt / .02), h = dt / n; n > 0; n--) { this.v += (this.k * (this.t - this.x) - this.c * this.v) * h; this.x += this.v * h; }
    if (Math.abs(this.v) < 4e-4 && Math.abs(this.t - this.x) < 4e-4) { this.x = this.t; this.v = 0; return false; }
    return true;
  }
  snap() { this.x = this.t; this.v = 0; }
}

/* ---------- textures (tiny canvases) and the materials ---------- */
function canvasTex(T, w, h, draw) {
  const c = D.createElement("canvas"); c.width = w; c.height = h; draw(c.getContext("2d"), w, h);
  const t = new T.CanvasTexture(c); t.colorSpace = T.SRGBColorSpace; t.anisotropy = 4; return t;
}
function radial(T, stops) {
  return canvasTex(T, 64, 64, (g, w, h) => { const r = g.createRadialGradient(w / 2, h / 2, 0, w / 2, h / 2, w / 2); for (const [p, c] of stops) r.addColorStop(p, c); g.fillStyle = r; g.fillRect(0, 0, w, h); });
}
function makeMaterials(T) {
  const tex = {
    ruled: canvasTex(T, 64, 64, (g, w, h) => { g.fillStyle = "#fff"; g.fillRect(0, 0, w, h); g.fillStyle = "rgba(26,28,32,.34)"; for (let y = 14; y < 58; y += 8) g.fillRect(8, y, w - 16 - (y === 14 ? 20 : 0), 1); }),
    edges: canvasTex(T, 64, 64, (g, w, h) => { g.fillStyle = "#fff"; g.fillRect(0, 0, w, h); g.fillStyle = "rgba(26,28,32,.22)"; for (let y = 1; y < h; y += 2) g.fillRect(0, y, w, 1); }),
    vane: canvasTex(T, 64, 64, (g, w, h) => {      /* a feather's barbs, and an ink-dark edge along its wide side (u near 1) so the vane reads against parchment */
      g.fillStyle = "#fff"; g.fillRect(0, 0, w, h); g.fillStyle = "rgba(26,28,32,.26)"; for (let y = 1; y < h; y += 2) g.fillRect(0, y, w, 1);
      const e = g.createLinearGradient(w * .62, 0, w, 0); e.addColorStop(0, "rgba(26,28,32,0)"); e.addColorStop(.7, "rgba(26,28,32,.55)"); e.addColorStop(1, "rgba(26,28,32,.9)"); g.fillStyle = e; g.fillRect(w * .62, 0, w * .38, h);
    }),
    coin: radial(T, [[0, "#fff"], [.7, "#fff"], [1, "#cde4da"]]),
    glow: radial(T, [[0, "rgba(255,232,176,1)"], [.42, "rgba(200,150,58,.45)"], [1, "rgba(200,150,58,0)"]]),
    shadow: radial(T, [[0, "rgba(0,0,0,.95)"], [.5, "rgba(0,0,0,.34)"], [1, "rgba(0,0,0,0)"]])
  };
  const P = o => new T.MeshPhysicalMaterial(o);
  const M = {
    brass: P({color: 0xC8963A, metalness: 1, roughness: .27, anisotropy: .6}),
    brassDark: P({color: 0x6E4C14, metalness: 1, roughness: .5}),
    verd: P({color: 0x2F6B5E, metalness: .08, roughness: .72, sheen: .25, sheenColor: 0x6DBBA8, sheenRoughness: .6, clearcoat: .12, clearcoatRoughness: .35}),
    parch: P({color: 0xF1E7D0, metalness: 0, roughness: .92}),
    ink: P({color: 0x1A1C20, metalness: 0, roughness: .5})
  };
  M.verdGloss = M.verd.clone(); M.verdGloss.clearcoat = .6; M.verdGloss.clearcoatRoughness = .18;
  M.ruled = M.parch.clone(); M.ruled.map = tex.ruled;
  M.edges = M.parch.clone(); M.edges.map = tex.edges;
  M.quill = M.parch.clone(); M.quill.side = T.DoubleSide; M.quill.map = tex.vane;      /* the fine lines read as the vane's barbs */
  M.coinFace = M.brass.clone(); M.coinFace.map = tex.coin; M.coinFace.anisotropy = .2; M.coinFace.roughness = .22;
  M.glow = new T.SpriteMaterial({map: tex.glow, transparent: true, depthWrite: false, toneMapped: false, blending: T.AdditiveBlending, opacity: 0});
  M.shadow = new T.SpriteMaterial({map: tex.shadow, transparent: true, depthWrite: false, toneMapped: false, opacity: 0});
  M.all = [M.brass, M.brassDark, M.verd, M.verdGloss, M.parch, M.ruled, M.edges, M.quill, M.ink, M.coinFace, M.glow, M.shadow];
  M.tex = Object.values(tex);
  return M;
}
function themeMaterials(M, t) {
  for (const m of [M.brass, M.coinFace]) { m.color.set(t.brass); m.roughness = m === M.coinFace ? t.brassR - .05 : t.brassR; }
  M.verd.color.set(t.verd); M.verdGloss.color.set(t.well);
  for (const m of [M.parch, M.ruled, M.edges, M.quill]) m.color.set(t.parch);
  for (const m of M.all) if (m.isMeshPhysicalMaterial) m.envMapIntensity = t.env;
  for (const m of [M.brass, M.brassDark, M.coinFace]) m.envMapIntensity = t.env * 1.5;      /* metal lives on what it reflects */
}
/* the room the objects reflect: three.js's own RoomEnvironment through PMREM, with two soft panels of our own (a window on the
   far wall and a lamp overhead, so that lids and coin faces reflect light, not a grey wall), or a studio gradient if it is missing */
function environment(T, Room, R) {
  const pm = new T.PMREMGenerator(R);
  let env = null;
  try {
    if (Room) {
      const room = new Room(), panel = (x, y, z, sx, sy, sz, k) => { const m = new T.Mesh(new T.BoxGeometry(), new T.MeshBasicMaterial({color: new T.Color().setScalar(k)})); m.position.set(x, y, z); m.scale.set(sx, sy, sz); room.add(m); };
      panel(0, 15, -13.2, 11, 7, .1, 26); panel(1, 26.4, 4, 9, .1, 7, 38);
      env = pm.fromScene(room, .04).texture; if (room.dispose) room.dispose();
    }
  } catch (e) { env = null; }
  if (!env) {
    const t = canvasTex(T, 64, 32, (g, w, h) => { const gr = g.createLinearGradient(0, 0, 0, h); gr.addColorStop(0, "#f4f2ed"); gr.addColorStop(.55, "#b9b3a9"); gr.addColorStop(1, "#3b3733"); g.fillStyle = gr; g.fillRect(0, 0, w, h); g.fillStyle = "#fff8ea"; g.fillRect(w * .08, h * .18, w * .2, h * .32); });
    t.mapping = T.EquirectangularReflectionMapping; env = pm.fromEquirectangular(t).texture; t.dispose();
  }
  pm.dispose(); return env;
}

/* ---------- geometry helpers: a rounded, bevelled slab (small bevels everywhere), a reeded coin, a quill ---------- */
function rrShape(T, w, h, r) {
  const s = new T.Shape(), x = w / 2, y = h / 2, rr = Math.max(0, Math.min(r, x, y));
  s.moveTo(-x + rr, -y); s.lineTo(x - rr, -y); s.absarc(x - rr, -y + rr, rr, -Math.PI / 2, 0, false);
  s.lineTo(x, y - rr); s.absarc(x - rr, y - rr, rr, 0, Math.PI / 2, false);
  s.lineTo(-x + rr, y); s.absarc(-x + rr, y - rr, rr, Math.PI / 2, Math.PI, false);
  s.lineTo(-x, -y + rr); s.absarc(-x + rr, -y + rr, rr, Math.PI, Math.PI * 1.5, false);
  return s;
}
/* w by h in the face (x, y), d deep (z), corners rounded r, the front and back edges bevelled b; centred on the origin */
function slab(T, w, h, d, r = .02, b = .01) {
  const depth = Math.max(.002, d - 2 * b);
  const g = new T.ExtrudeGeometry(rrShape(T, w - 2 * b, h - 2 * b, r), {depth, bevelEnabled: b > 0, bevelThickness: b, bevelSize: b, bevelSegments: 2, curveSegments: 6});
  g.translate(0, 0, -depth / 2);
  return g;
}
function coinGeo(T, r, h, n) {      /* a cylinder whose rim steps in and out every segment: reeding */
  const g = new T.CylinderGeometry(r, r, h, n, 1), p = g.attributes.position, step = TAU / n;
  for (let i = 0; i < p.count; i++) {
    const x = p.getX(i), z = p.getZ(i), rr = Math.hypot(x, z);
    if (rr < r - 1e-4) continue;
    const k = Math.round(Math.atan2(z, x) / step), f = (r + (k % 2 ? .004 : -.004)) / rr;
    p.setX(i, x * f); p.setZ(i, z * f);
  }
  g.computeVertexNormals(); return g;
}
function quillGeo(T) {      /* a vane tapering to a point along a gentle S, wider on one side as a feather is, and the path its shaft follows */
  const N = 36, pos = [], uv = [], idx = [];
  const P = t => new T.Vector3(.035 * Math.sin(TAU * t * .75) + .05 * t * t, t * 1.1, .02 * Math.sin(Math.PI * t));
  const W = t => { if (t < .26) return .014; const s = (t - .26) / .74; return .014 + .26 * Math.sin(Math.PI * Math.pow(s, .75)) * (1 - s * .35); };
  for (let i = 0; i <= N; i++) {
    const t = i / N, p = P(t), tg = (t < 1 ? P(t + 1e-3).sub(p) : p.clone().sub(P(t - 1e-3))).normalize(), n = new T.Vector3(-tg.y, tg.x, 0), w = W(t);
    const a = p.clone().addScaledVector(n, -w * .38), b = p.clone().addScaledVector(n, w * .62);
    pos.push(a.x, a.y, a.z, b.x, b.y, b.z); uv.push(0, t, 1, t);
    if (i) { const k = i * 2; idx.push(k - 2, k - 1, k, k - 1, k + 1, k); }
  }
  const g = new T.BufferGeometry();
  g.setAttribute("position", new T.Float32BufferAttribute(pos, 3)); g.setAttribute("uv", new T.Float32BufferAttribute(uv, 2)); g.setIndex(idx); g.computeVertexNormals();
  return {vane: g, path: new T.CatmullRomCurve3([0, .25, .5, .75, 1].map(P))};
}

/* ---------- the seven objects, each built about its own origin in design units, then fitted into a sphere ---------- */
const BUILD = {
  office(T, M) {      /* a nameplate: a brass plate leaning back on a verdigris block, two engraved bands where a name would be (no letters, ever) */
    const g = new T.Group();
    const base = new T.Mesh(slab(T, 1.06, .10, .42, .02, .012), M.verd); base.position.y = .05; g.add(base);
    const p = new T.Group(); p.position.set(0, .10, -.04); p.rotation.x = -rad(12); g.add(p);
    const plate = new T.Mesh(slab(T, 1.00, .34, .04, .02, .01), M.brass); plate.position.y = .17; p.add(plate);
    for (const [y, w] of [[.215, .60], [.13, .38]]) { const s = new T.Mesh(new T.BoxGeometry(w, .026, .008), M.brassDark); s.position.set(0, y, .021); p.add(s); }
    return g;
  },
  committees(T, M) {      /* three ruled sheets fanned about their foot, a brass clip over the top edge */
    const g = new T.Group();
    [-14, 0, 14].forEach((a, i) => {
      const h = new T.Group(); h.rotation.z = rad(a); h.position.z = (i - 1) * .022;
      const c = new T.Mesh(new T.BoxGeometry(.72, .90, .012), [M.parch, M.parch, M.parch, M.parch, M.ruled, M.ruled]); c.position.y = .45;
      h.add(c); g.add(h);
    });
    const pts = rrShape(T, .22, .40, .07).getSpacedPoints(64).map(v => new T.Vector3(v.x, v.y, 0));
    const clip = new T.Mesh(new T.TubeGeometry(new T.CatmullRomCurve3(pts, true, "centripetal"), 96, .02, 8, true), M.brass);
    clip.position.set(0, .76, .05); clip.rotation.z = rad(3); g.add(clip);
    return g;
  },
  howvotes(T, M) {      /* a gauge, not a clock: a verdigris plate, a brass bezel open at the foot (a 240 degree dial), a parchment face with
                           nine ink ticks, the needle two thirds of the way round, a brass hub; leaning back */
    const g = new T.Group(); g.rotation.x = -rad(20);
    const A0 = -rad(30), SWEEP = rad(240);      /* the dial runs from the lower right, over the top, to the lower left */
    const plate = new T.Mesh(slab(T, 1.16, 1.06, .07, .16, .012), M.verd); plate.position.set(0, .03, -.075); g.add(plate);
    const bezel = new T.Mesh(new T.TorusGeometry(.50, .05, 12, 48, SWEEP), M.brass); bezel.rotation.z = A0; g.add(bezel);
    for (const a of [A0, A0 + SWEEP]) { const cap = new T.Mesh(new T.SphereGeometry(.05, 12, 8), M.brass); cap.position.set(.50 * Math.cos(a), .50 * Math.sin(a), 0); g.add(cap); }
    const face = new T.Mesh(new T.CircleGeometry(.47, 48, A0, SWEEP), M.parch); face.position.z = -.02; g.add(face);
    const tick = new T.BoxGeometry(.016, .07, .008);
    for (let i = 0; i <= 8; i++) { const a = A0 + SWEEP * i / 8, m = new T.Mesh(tick, M.ink); m.position.set(.40 * Math.cos(a), .40 * Math.sin(a), -.012); m.rotation.z = a - Math.PI / 2; g.add(m); }
    const s = new T.Shape(); s.moveTo(-.032, -.09); s.lineTo(.032, -.09); s.lineTo(.009, .36); s.lineTo(-.009, .36); s.closePath();
    const at = A0 + SWEEP * (1 - .65);      /* the needle reads two thirds of the way from the dial's left end */
    const needle = new T.Mesh(new T.ExtrudeGeometry(s, {depth: .016, bevelEnabled: false}), M.verd); needle.rotation.z = at - Math.PI / 2; needle.position.z = -.004; g.add(needle);
    const hub = new T.Mesh(new T.SphereGeometry(.055, 20, 14), M.brass); hub.position.z = .012; g.add(hub);
    return g;
  },
  work(T, M) {      /* a quill rising from a lacquered inkwell with a brass collar; the vane's wide side is ink-dark and its shaft is brass */
    const g = new T.Group();
    const well = new T.Mesh(new T.CylinderGeometry(.26, .23, .34, 40), M.verdGloss); well.position.y = .17; g.add(well);
    const collar = new T.Mesh(new T.TorusGeometry(.25, .025, 10, 40), M.brass); collar.rotation.x = Math.PI / 2; collar.position.y = .34; g.add(collar);
    const ink = new T.Mesh(new T.CircleGeometry(.215, 40), M.ink); ink.rotation.x = -Math.PI / 2; ink.position.y = .335; g.add(ink);
    const q = new T.Group(); q.position.set(.03, .30, .02); q.rotation.z = -rad(35); q.rotation.y = -rad(20); g.add(q);
    const {vane, path} = quillGeo(T);
    q.add(new T.Mesh(vane, M.quill), new T.Mesh(new T.TubeGeometry(path, 28, .012, 6, false), M.brass));
    const nib = new T.Mesh(new T.ConeGeometry(.022, .10, 12), M.brass); nib.rotation.x = Math.PI; nib.position.y = -.03; q.add(nib);
    return g;
  },
  money(T, M) {      /* four reeded coins stacked a little askew, their faces touched with patina at the rim, a fifth leaning on them */
    const g = new T.Group(), geo = coinGeo(T, .30, .055, 96), mats = [M.brass, M.coinFace, M.coinFace];
    for (let i = 0; i < 4; i++) { const c = new T.Mesh(geo, mats); c.position.set(i % 2 ? .012 : -.012, .0275 + i * .057, i % 3 ? -.008 : .01); c.rotation.set(0, rad(i * 37), rad(i % 2 ? 2 : -1.6)); g.add(c); }
    const lean = new T.Group(); lean.position.set(.44, .285, .06); lean.rotation.z = rad(22); lean.rotation.y = -rad(15); g.add(lean);
    const c = new T.Mesh(geo, mats); c.rotation.x = Math.PI / 2; lean.add(c);
    return g;
  },
  votes(T, M) {      /* a ballot box: verdigris with chamfered edges, a brass slot plate on the lid, a ballot standing half in */
    const g = new T.Group();
    const box = new T.Mesh(slab(T, .90, .62, .62, .035, .028), M.verd); box.position.y = .31; g.add(box);
    const plate = new T.Mesh(slab(T, .50, .14, .022, .012, .005), M.brass); plate.rotation.x = -Math.PI / 2; plate.position.y = .631; g.add(plate);
    const slot = new T.Mesh(new T.BoxGeometry(.36, .008, .028), M.ink); slot.position.y = .642; g.add(slot);
    const ballot = new T.Mesh(new T.BoxGeometry(.42, .30, .01), [M.parch, M.parch, M.parch, M.parch, M.ruled, M.ruled]);
    ballot.position.y = .64; ballot.rotation.z = rad(8); ballot.rotation.y = -rad(4); g.add(ballot);
    return g;
  },
  wiki(T, M) {      /* an open book: two page blocks in a V on a verdigris cloth cover, an ink ribbon in the gutter; no brass, it is not an official record */
    const g = new T.Group();
    for (const s of [-1, 1]) {
      const h = new T.Group(); h.rotation.z = -s * rad(14); g.add(h);
      const cover = new T.Mesh(slab(T, .53, .69, .02, .012, .004), M.verd); cover.rotation.x = -Math.PI / 2; cover.position.set(s * .26, .01, 0); h.add(cover);
      const pages = new T.Mesh(new T.BoxGeometry(.50, .06, .66), [M.edges, M.edges, M.ruled, M.parch, M.edges, M.edges]); pages.position.set(s * .255, .05, 0); h.add(pages);
    }
    const ribbon = new T.Mesh(new T.BoxGeometry(.05, .005, .82), M.ink); ribbon.position.set(.02, .083, .04); ribbon.rotation.y = rad(5); g.add(ribbon);
    return g;
  },
  sheet(T, M) {      /* any tab this file does not know: one ruled sheet */
    const g = new T.Group(), c = new T.Mesh(new T.BoxGeometry(.72, .90, .012), [M.parch, M.parch, M.parch, M.parch, M.ruled, M.ruled]); c.position.y = .45; g.add(c); return g;
  }
};
function fit(T, obj, k) {      /* scales and centres an object so that its bounding box's sphere has radius RADIUS (the object fills about four fifths of its pocket) */
  obj.updateMatrixWorld(true);
  const b = new T.Box3().setFromObject(obj), c = b.getCenter(new T.Vector3()), s = b.getSize(new T.Vector3());
  const sc = (RADIUS * (k || 1)) / Math.max(1e-3, s.length() / 2);
  obj.position.copy(c).multiplyScalar(-sc); obj.scale.setScalar(sc);
  return -s.y * sc / 2;      /* where its foot is */
}
function makeIcon(T, M, id, i) {
  const root = new T.Group(), lift = new T.Group(), obj = (BUILD[id] || BUILD.sheet)(T, M), foot = fit(T, obj, K[id]);
  lift.add(obj); root.add(lift);
  const shadow = new T.Sprite(M.shadow.clone()); shadow.scale.set(1.5, .5, 1); shadow.position.y = foot - .05; shadow.renderOrder = -2;
  const glow = new T.Sprite(M.glow.clone()); glow.scale.set(2.2, 1.1, 1); glow.position.y = foot - .02; glow.renderOrder = -1;
  root.add(shadow, glow); root.visible = false;
  return {id, root, lift, shadow, glow, phase: i * 1.3, box: null, slot: null,
          sp: {lift: new Spring(0), scale: new Spring(1), glow: new Spring(0), yaw: new Spring(0), pitch: new Spring(0)}};
}

/* ---------- mount: one canvas over the rail, one renderer, every icon in its pocket ---------- */
export async function mount(host, items, opts = {}) {
  if (!host || !host.isConnected || !Array.isArray(items) || !items.length) return null;
  if (mq("(forced-colors: active)").matches) return null;
  let L; try { L = await lib(); } catch (e) { return null; }
  if (!host.isConnected) return null;
  const T = L.THREE, canvas = D.createElement("canvas");
  canvas.setAttribute("aria-hidden", "true"); canvas.className = "tabicons";
  canvas.style.cssText = "position:absolute;left:0;top:0;pointer-events:none;z-index:1;opacity:0;display:block";
  let R;
  try { R = new T.WebGLRenderer({canvas, alpha: true, antialias: true, premultipliedAlpha: true, powerPreference: "low-power", failIfMajorPerformanceCaveat: opts.caveat !== false}); }
  catch (e) { return null; }
  try { if (getComputedStyle(host).position === "static") host.style.position = "relative"; } catch (e) {}
  host.appendChild(canvas);
  R.setClearColor(0, 0); R.autoClear = false; R.toneMapping = T.ACESFilmicToneMapping; R.outputColorSpace = T.SRGBColorSpace;
  const scene = new T.Scene(), cam = new T.PerspectiveCamera(28, 1, .5, 30);
  cam.position.set(0, .80, 5.4); cam.lookAt(0, .05, 0);      /* the sphere of radius .9 spans the pocket; the drawn box is wider for the lift and the glow */
  const key = new T.DirectionalLight(0xFFF2DC, 2.4); key.position.set(-1.0, 1.9, 2.2);
  const rim = new T.DirectionalLight(0xDCE9FF, 1.2); rim.position.set(1.6, 1.2, -1.4);
  const hemi = new T.HemisphereLight(0xF5F5F2, 0x6E6A5E, .35);
  scene.add(key, rim, hemi);
  const M = makeMaterials(T);
  let env = null; try { env = environment(T, L.Room, R); scene.environment = env; } catch (e) { env = null; }
  const built = new Map(), fine = mq("(hover: hover) and (pointer: fine)"), reduced = mq("(prefers-reduced-motion: reduce)"), scheme = mq("(prefers-color-scheme: dark)");
  let icons = [], selected = null, hovered = null, focused = null, explicitHover = false, pointer = null, pointerIcon = null;
  let still = !!opts.still, dark = null, t = THEME.light, onscreen = true, raf = 0, last = 0, destroyed = false, size = {w: 0, h: 0}, dpr = 1, frames = 0;
  const stillNow = () => still || reduced.matches || H.classList.contains("calm") || calmNow();

  function applyTheme() {
    const d = isDark(); if (d === dark) return; dark = d; t = THEME[d ? "dark" : "light"];
    themeMaterials(M, t); R.toneMappingExposure = t.exposure; key.intensity = t.key; rim.intensity = t.rim; hemi.intensity = t.hemi;
  }
  function setItems(list) {
    icons = [];
    for (const it of (list || [])) {
      if (!it || !it.id || !it.slot) continue;
      let ic = built.get(it.id);
      if (!ic) { ic = makeIcon(T, M, it.id, built.size); built.set(it.id, ic); scene.add(ic.root); }
      ic.slot = it.slot; icons.push(ic);
    }
    const has = id => id && icons.some(ic => ic.id === id);
    if (!has(selected)) selected = null; if (!has(hovered)) hovered = null; if (!has(focused)) focused = null;
    if (ro) { ro.disconnect(); ro.observe(host); for (const ic of icons) ro.observe(ic.slot); }
    request();
  }
  /* where each pocket is, relative to the canvas (one rect each; the canvas scrolls with the rail's content), and the
     canvas sized to cover the rail and every pocket's box */
  function measure() {
    const cr = canvas.getBoundingClientRect();
    let mx = 0, my = 0;
    for (const ic of icons) {
      const r = ic.slot.getBoundingClientRect(), s = Math.max(r.width, r.height, 16), b = s * BOX;
      ic.box = {x: r.left + r.width / 2 - b / 2 - cr.left, y: r.top + r.height / 2 - b / 2 - cr.top, s: b, cx: r.left + r.width / 2, cy: r.top + r.height / 2, on: r.width > 0 && r.height > 0};
      if (ic.box.on) { mx = Math.max(mx, ic.box.x + b); my = Math.max(my, ic.box.y + b); }
    }
    const w = Math.max(1, host.clientWidth, Math.ceil(mx) + 2), h = Math.max(1, host.clientHeight, Math.ceil(my) + 2), d = Math.min(2, window.devicePixelRatio || 1);
    if (w !== size.w || h !== size.h || d !== dpr) { size = {w, h}; dpr = d; R.setPixelRatio(d); R.setSize(w, h, false); canvas.style.width = w + "px"; canvas.style.height = h + "px"; }
  }
  function draw(dt, now) {
    if (destroyed) return false;
    measure(); frames++;
    const st = stillNow(), fineP = fine.matches, hov = explicitHover ? hovered : pointerIcon;
    let moving = false;
    R.setScissorTest(false); R.clear(); R.setScissorTest(true);
    for (const ic of icons) {
      const sel = ic.id === selected, h = ic.id === hov, f = ic.id === focused, sp = ic.sp;
      sp.lift.t = sel ? LIFT.selected : (h || f) ? LIFT.hover : 0;
      sp.scale.t = sel ? SCALE_SEL : 1;
      sp.glow.t = sel ? t.glow : f ? t.glow * .9 : h ? t.glow * .5 : 0;
      let ly = 0, lp = 0;
      if (h && pointer && fineP && ic.box.on) { ly = clamp((pointer.x - ic.box.cx) / 60, -1, 1) * 18; lp = clamp((pointer.y - ic.box.cy) / 60, -1, 1) * 12; }
      sp.yaw.t = ly; sp.pitch.t = lp;
      if (st) for (const k in sp) sp[k].snap(); else for (const k in sp) if (sp[k].step(dt)) moving = true;
      const amp = st ? 0 : sel ? 5 : 11, ph = ic.phase;
      const idle = amp * Math.sin(TAU * (now / 9000 - ph / 9)), bob = st ? 0 : .012 * DIAM * Math.sin(TAU * (now / 4200 - ph / 4.2));
      ic.lift.rotation.set(rad(POSE.pitch + (PITCH[ic.id] || 0) + sp.pitch.x), rad(POSE.yaw + idle + sp.yaw.x), 0);
      ic.lift.position.y = sp.lift.x * DIAM + bob; ic.lift.scale.setScalar(sp.scale.x);
      ic.shadow.material.opacity = t.shadow * Math.max(.4, 1 - sp.lift.x * 4); ic.shadow.scale.set(1.5 * (1 + sp.lift.x), .5 * (1 + sp.lift.x), 1);
      ic.glow.material.opacity = sp.glow.x;
      if (!ic.box.on) continue;
      const b = ic.box, y = size.h - (b.y + b.s);
      ic.root.visible = true;
      R.setViewport(b.x, y, b.s, b.s); R.setScissor(b.x, y, b.s, b.s);
      R.render(scene, cam);
      ic.root.visible = false;
    }
    return moving || !st;      /* with motion on the idle turn never stops, so the loop runs while the rail is on screen */
  }
  function request() { if (!raf && !destroyed) raf = requestAnimationFrame(frame); }
  function frame(now) {
    raf = 0;
    const dt = last ? Math.min(.05, (now - last) / 1000) : 1 / 60; last = now;
    if (draw(dt, now) && onscreen && !D.hidden) request(); else last = 0;
  }
  function iconAt(e) {
    for (const ic of icons) { const el = ic.slot.closest("[role=tab],button,a") || ic.slot.parentElement; if (el && el.contains(e.target)) return ic.id; }
    return null;
  }
  const onPointer = e => { if (e.pointerType && e.pointerType !== "mouse") return; pointer = {x: e.clientX, y: e.clientY}; pointerIcon = iconAt(e); request(); };
  const onLeave = () => { pointer = null; pointerIcon = null; request(); };
  const onVis = () => { if (!D.hidden) request(); };
  const onTheme = () => { applyTheme(); request(); };
  host.addEventListener("pointermove", onPointer, {passive: true}); host.addEventListener("pointerleave", onLeave, {passive: true});
  host.addEventListener("scroll", request, {passive: true}); host.addEventListener("transitionend", request);
  addEventListener("resize", request); D.addEventListener("visibilitychange", onVis);
  reduced.addEventListener("change", request); scheme.addEventListener("change", onTheme);
  const ro = "ResizeObserver" in window ? new ResizeObserver(request) : null;
  const io = "IntersectionObserver" in window ? new IntersectionObserver(es => { for (const e of es) onscreen = e.isIntersecting; if (onscreen) request(); }) : null;
  if (io) io.observe(host);
  const mo = new MutationObserver(onTheme); mo.observe(H, {attributes: true, attributeFilter: ["data-theme", "data-contrast", "data-calm", "class"]});
  const onStore = e => { if (!e.key || e.key === "tca.a11y.v1") request(); };
  addEventListener("storage", onStore);

  function destroy() {
    if (destroyed) return; destroyed = true;
    if (raf) cancelAnimationFrame(raf); raf = 0;
    host.removeEventListener("pointermove", onPointer); host.removeEventListener("pointerleave", onLeave);
    host.removeEventListener("scroll", request); host.removeEventListener("transitionend", request);
    removeEventListener("resize", request); D.removeEventListener("visibilitychange", onVis);
    reduced.removeEventListener("change", request); scheme.removeEventListener("change", onTheme); removeEventListener("storage", onStore);
    if (ro) ro.disconnect(); if (io) io.disconnect(); mo.disconnect();
    for (const ic of built.values()) { ic.root.traverse(o => { if (o.geometry) o.geometry.dispose(); }); ic.shadow.material.dispose(); ic.glow.material.dispose(); }
    for (const m of M.all) m.dispose(); for (const x of M.tex) x.dispose(); if (env) env.dispose();
    R.dispose(); try { R.forceContextLoss(); } catch (e) {}
    canvas.remove(); host.classList.remove("icons3d");
  }
  const ctl = {
    select(id) { selected = id || null; request(); },
    hover(id) { explicitHover = true; hovered = id || null; request(); },
    focus(id) { focused = id || null; request(); },
    setStill(v) { still = !!v; request(); },
    setItems, destroy,
    /* beyond the contract, for the lab and for checks: the canvas, one frame now, every spring at rest, and the cost of a frame */
    canvas, draw: () => draw(0, performance.now()),
    settle() { const now = performance.now(); draw(0, now); for (const ic of icons) for (const k in ic.sp) ic.sp[k].snap(); return draw(0, now); },
    bench(n = 60) {
      const gl = R.getContext(); let cpu = 0, all = 0;
      R.info.autoReset = false;
      for (let i = 0; i < n; i++) { R.info.reset(); const a = performance.now(); draw(1 / 60, a); const b = performance.now(); gl.finish(); all += performance.now() - a; cpu += b - a; }
      const inf = R.info.render; R.info.autoReset = true;
      return {frames: n, cpuMs: +(cpu / n).toFixed(2), frameMs: +(all / n).toFixed(2), calls: inf.calls, triangles: inf.triangles, px: `${size.w * dpr}x${size.h * dpr}`, icons: icons.length};
    },
    get ids() { return icons.map(ic => ic.id); }, get still() { return stillNow(); }, get dark() { return !!dark; }, get frames() { return frames; }
  };
  applyTheme(); setItems(items);
  draw(0, performance.now());
  canvas.style.transition = H.classList.contains("calm") || reduced.matches ? "none" : "opacity .3s ease";
  setTimeout(() => { if (!destroyed) canvas.style.opacity = "1"; }, 0);
  request();
  return ctl;
}
