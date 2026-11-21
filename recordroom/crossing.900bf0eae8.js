/*
 The reading room: the way into the record, the bills and legislatures side (John, 2026-10-11: "the Library of Congress
 Main Reading Room ... under the great dome, reading desks and stacks; a bound volume of the record opens in front of
 you"), and, from the same scene, the place a reader can enter and sit in as long as they like ("just enter, sit in a
 space and enjoy it").

 The crossing (ten seconds). You stand at a reading desk in the Main Reading Room of the Thomas Jefferson Building, among
 the mahogany desks in their rings around the central desk, their brass-hooded lamps lit, the afternoon sun lying across
 the room in shafts with the dust turning in them. Your eyes rise past the alcoves of books, the marble screens and the
 bronze figures on the balustrades, the great arches with their stained-glass windows and the figures between them, to
 the coffered dome, the painted collar and the lantern, and come back down to the desk in front of you. A bound volume of
 the Congressional Record is set down there; it falls open, and as its pages turn you straighten up and step back, the
 room standing round the record open on your desk. The room fades into the record.

 The place. A reader starts seated where they chose: at that desk, in the visitors' gallery high in the west alcove (where
 the gallery photograph was taken from), or inside the counter of the central desk; looks around by dragging, by touch or
 with the arrow keys; gets up and walks the floor (W A S D or the arrows; on a phone a button held to walk the way they
 look), through the aisles and in at the central desk's gate but never through a wall or a desk; and sits again with a
 tap. The sound of the room is off until they turn it on, and is made on the device. Nothing about the reader is sent.

 How it is made. The room is two photographs by Carol M. Highsmith, which she gave to the Library of Congress with no known
 restrictions: the room from its upper gallery, and the dome from the floor. Each was measured against the room's own
 dimensions (the 1897 handbook of the building: an octagon a hundred feet across, the dome a half circle a hundred feet wide
 springing from seventy-five feet up, its 320 coffers in eight rows), which fixes where each camera stood and which way it
 looked to a fraction of a degree. The room is built as plain geometry in its real proportions and each photograph is cast
 back onto it from where it was taken, so the walls, arches and dome are the photographs themselves, at their true depth;
 where a photograph could not see (inside an alcove, round the back of a pier, behind a statue), the same place mirrored
 across the nearest pier or in a neighbouring bay is used, since the eight bays are alike; each pier, with its statue on
 its pedestal, takes the photograph of one pier seen from in front. The near things are built and lit here: the desks in
 their rings at the radii the photographs show, with the varnish worn and scratched where readers have sat, the lamps
 (brass hoods, as in the room; not green glass), the chairs, the carpet with its rosettes and wreathed books, the central
 desk, and the volume itself, its leather from a CC0 photograph and its pages set here. The desks and the book are lit by
 the lamps, by the sun where a shaft lands, and by the room's own photographs, taken again from wherever the reader sits.
 The screen gets it all through a lens (the Lens class): a high-range picture with depth, a soft bloom off the windows and
 the lamps, depth of field with the focus racking between the page and the room, the shafts of sun as an exact line
 integral through each, a filmic tone curve, a quiet grade, the lens's fall-off at the edges and a very fine grain. The
 place loads the two photographs at the size that holds up close (the gallery view at its crop's native 5,550 pixels, the
 dome at 6,144) on a computer that can draw them, about 12 MB in all; a phone or a lean device gets the crossing's own
 light set, about 2 MB.

 Uses three.js (MIT licence), kept with the site.
   prepare(opts)           fetch the crossing's files (on the first hover, focus or tap of a way into the record);
                           opts.lean the lighter files and drawing (by default, a device with little memory or few cores)
   prepareRoom(opts)       the place's files (the big photographs on a computer); opts.onProgress(bytes, total)
   supported()             can this device draw it
   run(url, opts)          play the crossing over the page, then go to url; false when it cannot be drawn. Returns
                           {skip, stay}. opts.host  the element to draw into; opts.assets  what prepare() returned;
                           opts.still  one still picture, then a fade; opts.lean  the light version; opts.fade  called
                           before the still's fade; opts.start, opts.end  the colours it fades in from and out to (CSS
                           colours); opts.stay  the room's own page, for a "Stay here" button (any element with data-stay
                           on the veil keeps its own presses; stay() hands this view over through sessionStorage
                           "tca.record.stay" and goes there); opts.hold()  true while the reader reaches for Stay;
                           opts.keys false  the caller listens for keys itself
   enter(canvas, opts)     the place (see the comment above enter); returns its controller
   still(t, w, h, opts)    one frame as a JPEG data URL (opts.png: a PNG), for checking a scene where frames are not drawn
                           (a Promise of {url, info}); opts.still the still picture; opts.lean the light version;
                           opts.room the place, from opts.seat or opts.walk
   SEATS, STILL_T, DUR     the seats, the moment the still picture shows, and the length of the crossing in seconds
 A click, a tap or any key skips (a modifier or lock key alone does not, nor a key pressed with Ctrl, Alt or the command
 key). On leaving, sessionStorage "tca.record.arrive" says how: full, skip or still. Back while it plays stops it.
*/
import * as THREE from "../vendor/three.module.min.js";

const FILES = {"walls":"walls.ad243b6292.webp","walls_lean":"walls_lean.2407198b08.webp","walls_hi":"walls_hi.820565bb92.webp","dome":"dome.2fe11f15d6.webp","dome_lean":"dome_lean.d529a91787.webp","dome_hi":"dome_hi.bf2c5b659b.webp","wood_diff":"wood_diff.fe387f7bb1.jpg","wood_nor":"wood_nor.bd1bc8c051.jpg","wood_rough":"wood_rough.cd9abe162d.jpg","leather_diff":"leather_diff.d7fc11627a.jpg","leather_nor":"leather_nor.e5f9da4fcd.jpg","carpet_nor":"carpet_nor.05c63ca90e.jpg"};
const asset = k => new URL(FILES[k], import.meta.url).href;
export const DUR = 10.0;
export const STILL_T = 8.55;
const FT = 0.3048;                       // the handbook's feet, in metres
const D2R = Math.PI / 180;
const clamp = (x, a = 0, b = 1) => Math.max(a, Math.min(b, x));
const seg = (t, a, b) => clamp((t - a) / (b - a));
const smooth = x => x * x * (3 - 2 * x);
const inOut = x => x < .5 ? 4 * x * x * x : 1 - Math.pow(-2 * x + 2, 3) / 2;
const sine = x => 0.5 - 0.5 * Math.cos(Math.PI * x);      // a head turning: gentle at both ends, never sudden in the middle
const mix = (a, b, t) => a + (b - a) * t;
const V3 = (x = 0, y = 0, z = 0) => new THREE.Vector3(x, y, z);
const dirAz = a => V3(Math.cos(a * D2R), 0, Math.sin(a * D2R));      // a direction on the floor: 0 east, + toward the south
function rng(seed){ let a = seed >>> 0; return () => { a |= 0; a = a + 0x6D2B79F5 | 0; let t = Math.imul(a ^ a >>> 15, 1 | a); t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t; return ((t ^ t >>> 14) >>> 0) / 4294967296; }; }
const pt = {x: 0, y: 0, sx: 0, sy: 0};      // the pointer, -1 to 1 across the window; sx, sy follow it slowly, as a head does
addEventListener("pointermove", e => { pt.x = e.clientX / innerWidth * 2 - 1; pt.y = e.clientY / innerHeight * 2 - 1; }, {passive: true});

/* ================================ the two photographs, as the cameras that took them ================================ */
/* World: metres, x east, y up, z south; the room's centre on the floor is the origin. Each camera: where it stood, its
   right, up and forward directions, its focal length and centre in the pixels of the file kept here (the lean files are
   half the size). Found by fitting the dome's coffers, seen in both photographs, to the dome's known shape. */
const PHOTO = {
  walls: {pos: [-17.5364, 12.1546, -0.335], R: [-0.037071, 0, 0.999313], U: [0, 1, 0], F: [0.999313, 0, 0.037071],
          f: 2041.990, cx: 1599.623, cy: 1348.542, w: 3072, h: 2214},
  dome:  {pos: [0.102, 3.1416, -0.1873], R: [-0.99833, -0.024493, -0.052324], U: [0.052795, -0.019004, -0.998425], F: [-0.023461, 0.999519, -0.020265],
          f: 1652.352, cx: 1255.713, cy: 956.477, w: 2560, h: 1921}
};

/* ================================ the room's proportions (feet) ================================ */
/* From the handbook and from the photographs, read by casting their pixels onto the room's planes. */
const ROOM = {
  Rs: 51.5,          // the screens' faces: the octagon between the piers, from the centre
  Ua: 15.0,          // half the width of an alcove's opening
  Wa: 14.0,          // an alcove's depth behind its screen
  s1c: [0, 8.6, 11.8, 16.1],      // the first storey's central arch: centre, width, springing, crown
  s1s: [9.4, 5.6, 13.2, 16.0],    // its two side arches: offset, width, springing, crown
  s1sill: 2.6,                    // the side arches' sill
  H1: 18.6,          // the alcoves' second floor
  s2: [7, 3.15, 26.5, 30.3, 22.4],   // the second storey: number of arches, width, springing, crown, sill
  Hg: 33.6,          // the gallery's floor, at the top of the screens
  Hb: 36.1,          // the balustrade's rail
  Ent0: 43.1, Ent1: 50.4,          // the lower entablature along the alcoves' back walls and over the piers
  Arch: [17.4, 54.6],              // the great arches: radius, springing
  Win: [16.2, 53.9],               // the windows at the back of the alcoves: radius, springing
  Rp: 53.0, Wp: 6.2,               // the piers' fronts: distance from the centre, half width
  Rcc: 52.2, Rc: 2.3,              // the engaged columns: centre's distance, radius
  PierBase: 11.0, PierTop: 44.0,   // the piers' high base, and the top of their capitals
  Plinth: 53.3,                    // the symbolic statues' pedestals, on the entablature over each pier, are this high
  Statue: 12.2,                    // and the statues stand a little over eleven feet (read off the gallery photograph)
  Rue: 47.0, Ue0: 74.0, Ue1: 86.0, // the upper entablature's ring: radius, bottom, top
  Rd: 50.5, Hd: 75.0, ThL: 15.0,   // the dome: radius of its coffers' grounds, its centre's height, the lantern's opening (degrees from the top)
  LanternTop: 158.0
};

/* ================================ the furniture's places (metres) ================================ */
/* The rings of desks as the gallery photograph shows them (the lamps of each ring back-projected to the floor): the
   reference ring at 20 feet, the two rings of double-faced desks at 30.6 and 40.8 feet, eight desks to a ring with aisles
   between them on the bays' axes; the central desk's counter at 14.5 feet; a lamp to every four feet. */
const LAY = {
  rings: [{rc: 19.8 * FT, kind: "ref"}, {rc: 30.6 * FT, kind: "desk"}, {rc: 40.8 * FT, kind: "desk"}],
  aisle: 5.0 * FT, lampStep: 4.0 * FT,
  hw: 0.085, depth: 0.76,          // a desk's spine (half its width) and the depth of each face's top
  top: 0.762, glass: 0.006, spine: 0.875,
  hood: [0.46, 0.075, 0.15], hoodY: 1.13,
  eyeR: 34.65 * FT, eyeY: 1.6
};
/* the desk you stand at: on the middle ring, a lamp's width west-north-west of the centre of its desk */
LAY.heroRing = 1;
LAY.heroSeg = 202.5;
LAY.heroAz = LAY.heroSeg - LAY.lampStep / LAY.rings[1].rc / D2R;

/* ================================ the seats, and the sun ================================ */
/* Where a reader can sit in the room (John, 2026-10-11): at a reading desk on the middle ring (the crossing's own desk),
   in the visitors' gallery above the west alcove (where the gallery photograph was taken from), and inside the central
   desk's counter. For each: its name and a sentence for the page, the height of the eyes above its floor when seated,
   and where it is (worked out in build(), from the room's measurements). */
export const SEATS = [
  {id: "desk", name: "A reading desk", eye: 1.17,
   where: "At a desk on the middle ring, under your own lamp, facing the central desk across the room."},
  {id: "gallery", name: "The visitors’ gallery", eye: 1.28,
   where: "High in the west alcove, behind the balustrade, where visitors look down on the whole room."},
  {id: "centre", name: "The central desk", eye: 1.26,
   where: "Inside the round counter at the centre, where the librarians sit, with the rings of desks all around."}
];
const STAND_EYE = 1.62, WALK_SPEED = 1.25;      // standing eyes, and a walking pace, in metres (and metres a second)
/* The afternoon sun: toward it from the room (east, up, south), as a unit vector. It comes in through the south-east and
   south windows and lies across the room in shafts; the south-west window takes it at a grazing angle. */
const SUN = V3(0.1, 0.72, 0.69).normalize();
const SUN_BAYS = [[1, 0.8], [2, 1.0], [3, 0.6]];      // the bays whose windows the sun comes through, and how strongly

/* ================================ the files ================================ */
let loading = null, loadingLean = null, flips = null;
function image(url){ return new Promise((ok, no) => { const im = new Image(); im.decoding = "async"; im.onload = () => ok(im); im.onerror = () => no(new Error("could not load " + url)); im.src = url; }); }
/* a lean device (little memory or few cores) gets the light version: pages on the whole shell say so on <html>, as the
   gates ask; elsewhere the device is asked in the same way */
function autoLean(){
  const v = document.documentElement.getAttribute("data-lean");
  if (v) return v === "on";
  try { const n = navigator; return !!((n.deviceMemory && n.deviceMemory < 4) || (n.hardwareConcurrency && n.hardwareConcurrency <= 4)); } catch (e) { return false; }
}
/* Can this browser decode a picture off the page's thread already turned upside down (as the GPU wants it)? Tried on a
   two-pixel picture, once; where it cannot, the photographs are plain images */
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
/* a file fetched with its progress reported (bytes so far, and the total when the server says it), for the place's
   loading view */
async function fetchBlob(url, onBytes){
  const r = await fetch(url);
  if (!r.ok) throw new Error("could not load " + url);
  if (!onBytes || !r.body || !r.body.getReader) return r.blob();
  const total = +r.headers.get("content-length") || 0, reader = r.body.getReader(), parts = [];
  let got = 0;
  for (;;) { const {done, value} = await reader.read(); if (done) break; parts.push(value); got += value.byteLength; onBytes(got, total); }
  return new Blob(parts);
}
async function photo(url, onBytes){
  if (window.createImageBitmap && await flipsBitmaps()) {
    try { const b = await fetchBlob(url, onBytes); return await createImageBitmap(b, {imageOrientation: "flipY", premultiplyAlpha: "none"}); } catch (e) {}
  }
  return image(url);
}

const breathe = () => new Promise(r => setTimeout(r, 0));      // a moment for the page between pictures
const opt = k => FILES[k] ? image(asset(k)).catch(() => null) : Promise.resolve(null);
/* one set of files: the two photographs named, the materials, and the pictures drawn here */
async function loadSet(wallsKey, domeKey, lean, onProgress){
  const got = {}, report = () => { if (!onProgress) return; let b = 0, t = 0; for (const k in got) { b += got[k][0]; t += got[k][1]; } onProgress(b, t); };
  const prog = k => { got[k] = [0, 0]; return (b, t) => { got[k] = [b, t || got[k][1]]; report(); }; };
  const [walls, dome, woodD, woodN, woodR, leatherD, leatherN, carpetN] = await Promise.all([photo(asset(wallsKey), onProgress && prog("walls")), photo(asset(domeKey), onProgress && prog("dome")),
    opt("wood_diff"), opt("wood_nor"), opt("wood_rough"), opt("leather_diff"), opt("leather_nor"), opt("carpet_nor")]);
  const pics = {pages: {}};
  pics.carpet = carpetCanvas(lean); await breathe();
  pics.medallion = medallionCanvas(); pics.spines = spinesCanvas(lean); pics.edges = edgesCanvas(); pics.wear = wearCanvas(lean); await breathe();
  pics.cover = coverCanvases(leatherD, lean); await breathe();
  for (const [k, o] of Object.entries(PAGES)) { pics.pages[k] = pageCanvas(o, lean); await breathe(); }
  return {walls, dome, lean, kw: walls.width / PHOTO.walls.w, kd: dome.width / PHOTO.dome.w, wood: [woodD, woodN, woodR], leather: [leatherD, leatherN], carpetN, pics};
}
export function prepare(opts = {}){
  const lean = opts.lean != null ? !!opts.lean : autoLean();
  if (loading && loadingLean === lean) return loading;
  loadingLean = lean;
  loading = loadSet(lean ? "walls_lean" : "walls", lean ? "dome_lean" : "dome", lean);
  loading.catch(() => { loading = null; });
  return loading;
}
/* The biggest size of picture this device draws, asked once (a context that is let go at once) */
let maxTex = 0;
function maxTexture(){
  if (maxTex) return maxTex;
  try { const g = document.createElement("canvas").getContext("webgl2"); if (g) { maxTex = g.getParameter(g.MAX_TEXTURE_SIZE) || 4096; const x = g.getExtension("WEBGL_lose_context"); if (x) x.loseContext(); } } catch (e) {}
  return maxTex || 4096;
}
/* The place's own files (John, 2026-10-11: up to about 25 MB on a computer, 8 on a phone, fetched only on entering):
   the two photographs at the size that holds up close (the gallery view at its crop's native 5,550 pixels, the dome at
   6,144) on a computer that can draw them, the crossing's own set otherwise; the crossing's materials and pictures
   besides. opts.onProgress(bytes, total) reports the fetch; opts.hi forces or forbids the big set. */
let roomLoading = null, roomKey = "";
export function prepareRoom(opts = {}){
  const lean = opts.lean != null ? !!opts.lean : autoLean();
  let mem = 8; try { mem = navigator.deviceMemory || 8; } catch (e) {}
  /* a phone (a touch screen under 700 px on its short side) takes the crossing's own set, as a lean device does: the big set is
     for a computer that can draw it */
  let phone = false; try { phone = matchMedia("(pointer: coarse)").matches && Math.min(innerWidth, innerHeight) < 700; } catch (e) {}
  const hi = opts.hi != null ? !!opts.hi : (!lean && !phone && maxTexture() >= 8192 && mem >= 8 && !!FILES.walls_hi && !!FILES.dome_hi);
  const key = `${lean}/${hi}`;
  if (roomLoading && roomKey === key) return roomLoading;
  roomKey = key;
  roomLoading = (hi ? loadSet("walls_hi", "dome_hi", false, opts.onProgress) : prepare({lean})).then(A => Object.assign({}, A, {room: true, hi}));
  roomLoading.catch(() => { roomLoading = null; });
  return roomLoading;
}
export function supported(){
  try { const c = document.createElement("canvas"); return !!(window.WebGL2RenderingContext && c.getContext("webgl2")); } catch (e) { return false; }
}

/* ================================ geometry helpers ================================ */
/* Triangles gathered into one geometry: position, normal, uv (and a tag for the room). Each triangle is turned to face
   the way its normals say. */
class Mesher {
  constructor(){ this.p = []; this.n = []; this.u = []; this.t = []; }
  tri(a, b, c, na, nb, nc, ua, ub, uc, tag = 0){
    const g = new THREE.Vector3().subVectors(b, a).cross(new THREE.Vector3().subVectors(c, a));
    const want = V3().add(na).add(nb).add(nc);
    if (g.dot(want) < 0) { [b, c] = [c, b]; [nb, nc] = [nc, nb]; [ub, uc] = [uc, ub]; }
    for (const [q, m, w] of [[a, na, ua], [b, nb, ub], [c, nc, uc]]) { this.p.push(q.x, q.y, q.z); this.n.push(m.x, m.y, m.z); this.u.push(w[0], w[1]); this.t.push(tag); }
  }
  quad(a, b, c, d, n, uv = [[0, 0], [1, 0], [1, 1], [0, 1]], tag = 0){
    const N = n || new THREE.Vector3().subVectors(b, a).cross(new THREE.Vector3().subVectors(d, a)).normalize();
    this.tri(a, b, c, N, N, N, uv[0], uv[1], uv[2], tag); this.tri(a, c, d, N, N, N, uv[0], uv[2], uv[3], tag);
  }
  /* a box from its centre, its size and its axes (unit vectors), with uvs in metres */
  box(c, s, ax = [V3(1, 0, 0), V3(0, 1, 0), V3(0, 0, 1)], uvk = 1){
    const [X, Y, Z] = ax, h = [s[0] / 2, s[1] / 2, s[2] / 2];
    const P = (i, j, k) => c.clone().addScaledVector(X, i * h[0]).addScaledVector(Y, j * h[1]).addScaledVector(Z, k * h[2]);
    const faces = [[X, [1, -1, -1], [1, 1, -1], [1, 1, 1], [1, -1, 1], s[2], s[1]], [X.clone().negate(), [-1, -1, 1], [-1, 1, 1], [-1, 1, -1], [-1, -1, -1], s[2], s[1]],
                   [Y, [-1, 1, -1], [-1, 1, 1], [1, 1, 1], [1, 1, -1], s[2], s[0]], [Y.clone().negate(), [-1, -1, 1], [-1, -1, -1], [1, -1, -1], [1, -1, 1], s[2], s[0]],
                   [Z, [-1, -1, 1], [1, -1, 1], [1, 1, 1], [-1, 1, 1], s[0], s[1]], [Z.clone().negate(), [1, -1, -1], [-1, -1, -1], [-1, 1, -1], [1, 1, -1], s[0], s[1]]];
    for (const [n, a, b, cc, d, w, hh] of faces) this.quad(P(...a), P(...b), P(...cc), P(...d), n, [[0, 0], [w * uvk, 0], [w * uvk, hh * uvk], [0, hh * uvk]]);
  }
  /* a round post along Y from c, radius r, height h */
  cyl(c, r, h, n = 8, ax = [V3(1, 0, 0), V3(0, 1, 0), V3(0, 0, 1)]){
    const [X, Y, Z] = ax;
    for (let i = 0; i < n; i++) {
      const a0 = 2 * Math.PI * i / n, a1 = 2 * Math.PI * (i + 1) / n;
      const d0 = X.clone().multiplyScalar(Math.cos(a0)).addScaledVector(Z, Math.sin(a0)), d1 = X.clone().multiplyScalar(Math.cos(a1)).addScaledVector(Z, Math.sin(a1));
      const p0 = c.clone().addScaledVector(d0, r), p1 = c.clone().addScaledVector(d1, r);
      this.tri(p0, p1, p1.clone().addScaledVector(Y, h), d0, d1, d1, [0, 0], [r, 0], [r, h]);
      this.tri(p0, p1.clone().addScaledVector(Y, h), p0.clone().addScaledVector(Y, h), d0, d1, d0, [0, 0], [r, h], [0, h]);
    }
  }
  geometry(withTag){
    const g = new THREE.BufferGeometry();
    g.setAttribute("position", new THREE.Float32BufferAttribute(this.p, 3));
    g.setAttribute("normal", new THREE.Float32BufferAttribute(this.n, 3));
    g.setAttribute("uv", new THREE.Float32BufferAttribute(this.u, 2));
    if (withTag) g.setAttribute("aTag", new THREE.Float32BufferAttribute(this.t, 1));
    return g;
  }
}
/* a profile in (r, y) swept round the room's axis from angle a0 to a1 (radians); closed profiles are counter-clockwise.
   uvs: u along the arc, v along the profile, in metres */
function sweep(M, prof, a0, a1, n, closed = true, caps = false){
  const P = (r, y, a) => V3(r * Math.cos(a), y, r * Math.sin(a));
  if (closed) { let area = 0; for (let i = 0; i < prof.length; i++) { const [x0, y0] = prof[i], [x1, y1] = prof[(i + 1) % prof.length]; area += x0 * y1 - x1 * y0; }
    if (area < 0) prof = prof.slice().reverse(); }
  const m = prof.length, last = closed ? m : m - 1;
  let vlen = 0;
  for (let i = 0; i < last; i++) {
    const [r0, y0] = prof[i], [r1, y1] = prof[(i + 1) % m], er = r1 - r0, ey = y1 - y0, L = Math.hypot(er, ey) || 1e-6;
    const nr = ey / L, ny = -er / L, rm = (r0 + r1) / 2;
    for (let k = 0; k < n; k++) {
      const b0 = mix(a0, a1, k / n), b1 = mix(a0, a1, (k + 1) / n);
      const N0 = V3(nr * Math.cos(b0), ny, nr * Math.sin(b0)), N1 = V3(nr * Math.cos(b1), ny, nr * Math.sin(b1));
      const u0 = b0 * rm, u1 = b1 * rm;
      M.tri(P(r0, y0, b0), P(r1, y1, b0), P(r1, y1, b1), N0, N0, N1, [u0, vlen], [u0, vlen + L], [u1, vlen + L]);
      M.tri(P(r0, y0, b0), P(r1, y1, b1), P(r0, y0, b1), N0, N1, N1, [u0, vlen], [u1, vlen + L], [u1, vlen]);
    }
    vlen += L;
  }
  if (caps) for (const [a, s] of [[a0, -1], [a1, 1]]) {
    const tri = THREE.ShapeUtils.triangulateShape(prof.map(([r, y]) => new THREE.Vector2(r, y)), []);
    const N = V3(-Math.sin(a) * s, 0, Math.cos(a) * s);
    for (const [i, j, k] of tri) M.tri(P(...prof[i], a), P(...prof[j], a), P(...prof[k], a), N, N, N, [prof[i][0], prof[i][1]], [prof[j][0], prof[j][1]], [prof[k][0], prof[k][1]]);
  }
}
const rect = (r0, r1, y0, y1) => [[r0, y0], [r1, y0], [r1, y1], [r0, y1]];

/* ================================ the room, as geometry ================================ */
/* a bay's frame: u along the screen (toward the south at the east bay), y up, w back into the alcove; feet in, metres out */
function bayFrame(az){ const n = V3(Math.cos(az), 0, Math.sin(az)), t = V3(-Math.sin(az), 0, Math.cos(az));
  return (u, y, w, R = ROOM.Rs) => V3(0, 0, 0).addScaledVector(n, (R + w) * FT).addScaledVector(t, u * FT).setY(y * FT); }
function face(C, P, outline, holes, w, tag){
  const shape = new THREE.Shape(outline.map(([u, y]) => new THREE.Vector2(u, y)));
  for (const h of holes) shape.holes.push(new THREE.Path(h.map(([u, y]) => new THREE.Vector2(u, y))));
  const g = new THREE.ShapeGeometry(shape, 12), p = g.attributes.position, idx = g.index.array;
  for (let i = 0; i < idx.length; i += 3) {
    const v = [idx[i], idx[i + 1], idx[i + 2]].map(k => P(p.getX(k), p.getY(k), w));
    const n = new THREE.Vector3().subVectors(v[1], v[0]).cross(new THREE.Vector3().subVectors(v[2], v[0])).normalize();
    C.tri(v[0], v[1], v[2], n, n, n, [0, 0], [0, 0], [0, 0], tag);
  }
  g.dispose();
}
function archPath(uc, wid, ys, yc, ybot, n = 14){
  const r = wid / 2, pts = [[uc - r, ybot]], rise = yc - ys;
  for (let i = 0; i <= n; i++) { const a = Math.PI - Math.PI * i / n; pts.push([uc + r * Math.cos(a), ys + rise * Math.sin(a)]); }
  pts.push([uc + r, ybot]);
  return pts;
}
function buildRoom(){
  const R = ROOM, W = new Mesher(), D = new Mesher(), q = (a, b, c, d, tag) => W.quad(a, b, c, d, null, undefined, tag);
  for (let b = 0; b < 8; b++) {
    const az = b * 45 * D2R, P = bayFrame(az);
    /* the screen: two storeys of arches, the gallery's balustrade on top */
    const holes = [archPath(0, R.s1c[1], R.s1c[2], R.s1c[3], 0)];
    for (const s of [-1, 1]) holes.push(archPath(s * R.s1s[0], R.s1s[1], R.s1s[2], R.s1s[3], R.s1sill));
    const n2 = R.s2[0], pitch = (2 * R.Ua - 1.2) / n2;
    for (let i = 0; i < n2; i++) holes.push(archPath(-R.Ua + 0.6 + pitch * (i + 0.5), R.s2[1], R.s2[2], R.s2[3], R.s2[4]));
    face(W, P, [[-R.Ua, 0], [R.Ua, 0], [R.Ua, R.Hb], [-R.Ua, R.Hb]], holes, 0, 1);
    /* the alcove: its back wall, sides, floors and the gallery above */
    face(W, P, [[-R.Ua, 0], [R.Ua, 0], [R.Ua, R.Ent0], [-R.Ua, R.Ent0]], [], R.Wa, 2);
    for (const s of [-1, 1]) q(P(s * R.Ua, 0, 0), P(s * R.Ua, 0, R.Wa), P(s * R.Ua, R.Ent1, R.Wa), P(s * R.Ua, R.Ent1, 0), 3);
    for (const y of [0, R.H1, R.H1 - 0.8, R.Hg, R.Hg - 1.2]) q(P(-R.Ua, y, 0), P(R.Ua, y, 0), P(R.Ua, y, R.Wa), P(-R.Ua, y, R.Wa), 4);
    /* the lower entablature along the back wall, projecting a little */
    const E = 1.6;
    face(W, P, [[-R.Ua, R.Ent0], [R.Ua, R.Ent0], [R.Ua, R.Ent1], [-R.Ua, R.Ent1]], [], R.Wa - E, 5);
    q(P(-R.Ua, R.Ent0, R.Wa - E), P(R.Ua, R.Ent0, R.Wa - E), P(R.Ua, R.Ent0, R.Wa), P(-R.Ua, R.Ent0, R.Wa), 5);
    q(P(-R.Ua, R.Ent1, R.Wa - E), P(R.Ua, R.Ent1, R.Wa - E), P(R.Ua, R.Ent1, R.Wa), P(-R.Ua, R.Ent1, R.Wa), 5);
    /* the window wall inside the great arch, and the arch's soffit, a barrel vault from its face back to the window */
    const ar = R.Arch[0], ay = R.Arch[1], wy = R.Win[1], segs = 28, winTop = [];
    for (let i = 0; i <= segs; i++) { const a = Math.PI * i / segs; winTop.push([ar * Math.cos(a), wy + ar * Math.sin(a)]); }
    face(W, P, [[-ar, R.Ent1], [ar, R.Ent1], ...winTop], [], R.Wa, 6);
    for (let i = 0; i < segs; i++) {
      const a0 = Math.PI * i / segs, a1 = Math.PI * (i + 1) / segs, y0 = w => mix(ay, wy, w / R.Wa);
      const p = (a, w) => P(ar * Math.cos(a), y0(w) + ar * Math.sin(a), w);
      q(p(a0, 0), p(a1, 0), p(a1, R.Wa), p(a0, R.Wa), 7);
    }
    /* the arch's face and the spandrels round it, up to the upper entablature, and its jambs */
    const half = R.Rs * Math.tan(22.5 * D2R), arc = [];
    for (let i = 0; i <= 28; i++) { const a = Math.PI - Math.PI * i / 28; arc.push([ar * Math.cos(a), ay + ar * Math.sin(a)]); }
    face(W, P, [[-half, R.Ent1], [-ar, R.Ent1], ...arc, [ar, R.Ent1], [half, R.Ent1], [half, R.Ue0 + 1], [-half, R.Ue0 + 1]], [], 0, 8);
    for (const s of [-1, 1]) q(P(s * ar, R.Ent1, 0), P(s * ar, R.Ent1, R.Wa), P(s * ar, ay, R.Wa), P(s * ar, ay, 0), 7);
  }
  /* the piers, with their engaged columns and high bases, at the octagon's corners */
  for (let k = 0; k < 8; k++) {
    const az = (22.5 + 45 * k) * D2R, n = V3(Math.cos(az), 0, Math.sin(az)), t = V3(-Math.sin(az), 0, Math.cos(az));
    const at = (u, y, r) => V3(0, 0, 0).addScaledVector(n, r * FT).addScaledVector(t, u * FT).setY(y * FT);
    const R0 = ROOM.Rp, h = ROOM.Ent1;
    q(at(-ROOM.Wp, 0, R0), at(ROOM.Wp, 0, R0), at(ROOM.Wp, h, R0), at(-ROOM.Wp, h, R0), 10);
    const endL = bayFrame(az - 22.5 * D2R)(ROOM.Ua, 0, 0), endR = bayFrame(az + 22.5 * D2R)(-ROOM.Ua, 0, 0);
    for (const [e, u] of [[endL, -ROOM.Wp], [endR, ROOM.Wp]]) { const a = at(u, 0, R0), top = h * FT; q(a, e.clone(), e.clone().setY(top), a.clone().setY(top), 11); }
    const cc = n.clone().multiplyScalar(ROOM.Rcc * FT), rc = ROOM.Rc * FT, segs = 16;
    for (let i = 0; i < segs; i++) {
      const a0 = Math.PI * i / segs, a1 = Math.PI * (i + 1) / segs;
      const d0 = t.clone().multiplyScalar(Math.cos(a0)).addScaledVector(n, -Math.sin(a0)), d1 = t.clone().multiplyScalar(Math.cos(a1)).addScaledVector(n, -Math.sin(a1));
      const p0 = cc.clone().addScaledVector(d0, rc), p1 = cc.clone().addScaledVector(d1, rc);
      W.quad(p0.clone().setY(ROOM.PierBase * FT), p1.clone().setY(ROOM.PierBase * FT), p1.clone().setY(ROOM.PierTop * FT), p0.clone().setY(ROOM.PierTop * FT), d0.clone().add(d1).normalize(), undefined, 12);
    }
    { const rf = ROOM.Rcc - ROOM.Rc - 0.6, bw = ROOM.Wp + 0.4, hb = ROOM.PierBase;
      q(at(-bw, 0, rf), at(bw, 0, rf), at(bw, hb, rf), at(-bw, hb, rf), 14);
      q(at(-bw, hb, rf), at(bw, hb, rf), at(bw, hb, R0), at(-bw, hb, R0), 14);
      for (const s of [-1, 1]) q(at(s * bw, 0, rf), at(s * bw, 0, R0), at(s * bw, hb, R0), at(s * bw, hb, rf), 14); }
    q(at(-2.3, ROOM.Ent1, ROOM.Rcc - 1.5), at(2.3, ROOM.Ent1, ROOM.Rcc - 1.5), at(2.3, ROOM.Plinth, ROOM.Rcc - 1.5), at(-2.3, ROOM.Plinth, ROOM.Rcc - 1.5), 13);
    /* the entablature over the columns, standing out from the pier, that the pedestal stands on (its face, underside, top
       and ends); and the statue itself, a card at its own depth on the pedestal, so statue and pedestal hold together from
       wherever they are seen */
    { const re = ROOM.Rcc - ROOM.Rc - 0.4, bw = ROOM.Wp + 0.3, y0 = ROOM.PierTop, y1 = ROOM.Ent1, inward = n.clone().negate(), up = V3(0, 1, 0);
      W.quad(at(-bw, y0, re), at(bw, y0, re), at(bw, y1, re), at(-bw, y1, re), inward, undefined, 16);
      W.quad(at(-bw, y0, re), at(bw, y0, re), at(bw, y0, R0), at(-bw, y0, R0), up.clone().negate(), undefined, 16);
      W.quad(at(-bw, y1, re), at(bw, y1, re), at(bw, y1, R0), at(-bw, y1, R0), up, undefined, 16);
      for (const s of [-1, 1]) W.quad(at(s * bw, y0, re), at(s * bw, y0, R0), at(s * bw, y1, R0), at(s * bw, y1, re), t.clone().multiplyScalar(s), undefined, 16);
      const rs = ROOM.Rcc - 0.9, ys = ROOM.Plinth, yt = ROOM.Plinth + ROOM.Statue;
      W.quad(at(-2.6, ys, rs), at(2.6, ys, rs), at(2.6, yt, rs), at(-2.6, yt, rs), inward, undefined, 15); }
  }
  /* the upper entablature: a ring, its underside and its top out to the dome */
  const ring = 64, out = ROOM.Rs / Math.cos(22.5 * D2R);
  for (let i = 0; i < ring; i++) {
    const a0 = 2 * Math.PI * i / ring, a1 = 2 * Math.PI * (i + 1) / ring, p = (a, r, y) => V3(Math.cos(a) * r * FT, y * FT, Math.sin(a) * r * FT);
    const inward = V3(-Math.cos((a0 + a1) / 2), 0, -Math.sin((a0 + a1) / 2));
    W.quad(p(a0, ROOM.Rue, ROOM.Ue0), p(a1, ROOM.Rue, ROOM.Ue0), p(a1, ROOM.Rue, ROOM.Ue1), p(a0, ROOM.Rue, ROOM.Ue1), inward, undefined, 20);
    W.quad(p(a0, ROOM.Rue, ROOM.Ue0), p(a0, out, ROOM.Ue0), p(a1, out, ROOM.Ue0), p(a1, ROOM.Rue, ROOM.Ue0), V3(0, -1, 0), undefined, 21);
    W.quad(p(a0, ROOM.Rue, ROOM.Ue1), p(a1, ROOM.Rue, ROOM.Ue1), p(a1, ROOM.Rd, ROOM.Ue1), p(a0, ROOM.Rd, ROOM.Ue1), V3(0, 1, 0), undefined, 21);
  }
  /* the dome: a half sphere above the springing, open at the top to the lantern; the lantern's drum and its ceiling */
  const th0 = ROOM.ThL * D2R, thS = Math.acos(Math.min(1, (ROOM.Ue1 - ROOM.Hd) / ROOM.Rd)), nTh = 40, nPh = 128;
  const sp = (th, ph) => V3(Math.sin(th) * Math.cos(ph) * ROOM.Rd * FT, (ROOM.Hd + Math.cos(th) * ROOM.Rd) * FT, Math.sin(th) * Math.sin(ph) * ROOM.Rd * FT);
  for (let j = 0; j < nTh; j++) for (let i = 0; i < nPh; i++) {
    const t0 = mix(th0, thS, j / nTh), t1 = mix(th0, thS, (j + 1) / nTh), f0 = 2 * Math.PI * i / nPh, f1 = 2 * Math.PI * (i + 1) / nPh;
    const c = sp((t0 + t1) / 2, (f0 + f1) / 2).sub(V3(0, ROOM.Hd * FT, 0)).normalize().negate();
    D.quad(sp(t0, f0), sp(t1, f0), sp(t1, f1), sp(t0, f1), c, undefined, 30);
  }
  const rl = ROOM.Rd * Math.sin(th0), yl = ROOM.Hd + ROOM.Rd * Math.cos(th0);
  for (let i = 0; i < nPh; i++) {
    const f0 = 2 * Math.PI * i / nPh, f1 = 2 * Math.PI * (i + 1) / nPh, p = (ph, y, r = rl) => V3(Math.cos(ph) * r * FT, y * FT, Math.sin(ph) * r * FT);
    D.quad(p(f0, yl), p(f1, yl), p(f1, ROOM.LanternTop - 6), p(f0, ROOM.LanternTop - 6), V3(-Math.cos(f0), 0, -Math.sin(f0)), undefined, 31);
    D.tri(p(f0, ROOM.LanternTop - 6), p(f1, ROOM.LanternTop - 6), V3(0, ROOM.LanternTop * FT, 0), V3(0, -1, 0), V3(0, -1, 0), V3(0, -1, 0), [0, 0], [0, 0], [0, 0], 32);
  }
  return {walls: W.geometry(true), dome: D.geometry(true)};
}

/* ================================ the photographs on the room ================================ */
const PROJ_HEAD = `
uniform sampler2D uImg; uniform vec3 uPos, uR, uU, uF; uniform float uFx, uCx, uCy, uW, uH;
vec3 rotY(vec3 p, float a){ float c = cos(a), s = sin(a); return vec3(c * p.x - s * p.z, p.y, s * p.x + c * p.z); }
bool proj(vec3 P, out vec2 uv, out float zf){
  vec3 d = P - uPos; zf = dot(d, uF);
  if (zf < 0.05) return false;
  float x = (uCx + uFx * dot(d, uR) / zf) / uW, y = (uCy - uFx * dot(d, uU) / zf) / uH;
  uv = vec2(x, 1.0 - y);
  return x > 0.0015 && x < 0.9985 && y > 0.0015 && y < 0.9985;
}`;
/* k: the size of the picture kept here against the size the camera was fitted at (1 for the crossing's set, 0.5 for the
   lean set, larger for the place's) */
function photoUniforms(ph, tex, k){
  return {uImg: {value: tex}, uPos: {value: V3(...ph.pos)}, uR: {value: V3(...ph.R)}, uU: {value: V3(...ph.U)}, uF: {value: V3(...ph.F)},
          uFx: {value: ph.f * k}, uCx: {value: ph.cx * k}, uCy: {value: ph.cy * k}, uW: {value: ph.w * k}, uH: {value: ph.h * k}};
}
/* the photograph's camera, for its depth map: three.js cameras look down -z, so its axes are right, up and back */
function projectorCamera(ph, k, near = 0.5, far = 120){
  const f = ph.f * k, cx = ph.cx * k, cy = ph.cy * k, w = ph.w * k, h = ph.h * k;
  const cam = new THREE.PerspectiveCamera();
  cam.projectionMatrix.makePerspective(-cx / f * near, (w - cx) / f * near, cy / f * near, -(h - cy) / f * near, near, far);
  cam.projectionMatrixInverse.copy(cam.projectionMatrix).invert();
  const m = new THREE.Matrix4().makeBasis(V3(...ph.R), V3(...ph.U), V3(...ph.F).negate());
  m.setPosition(V3(...ph.pos)); cam.matrixAutoUpdate = false; cam.matrixWorld.copy(m); cam.matrixWorldInverse.copy(m).invert();
  return cam;
}
/* The walls take the gallery photograph. A point the photograph's camera did not see (facing away, hidden behind
   something nearer, or outside its frame) takes the same place in a neighbouring bay; inside an alcove, what the
   photograph saw through the alcove's opening. The screens' lowest band, which the photograph sees past the desks, is the
   brown Tennessee marble it is, drawn plainly. */
function wallsMaterial(tex, depthTex, k, U){
  return new THREE.ShaderMaterial({
    uniforms: Object.assign(photoUniforms(PHOTO.walls, tex, k), {uDepth: {value: depthTex}, uFar: {value: 120}, uExpo: U.uExpo, uRs: {value: ROOM.Rs * FT},
      uBaseCol: {value: new THREE.Color(0.105, 0.052, 0.040)}, uDebug: {value: 0}}),
    vertexShader: `attribute float aTag; varying vec3 vW, vN; varying float vTag;
      void main(){ vec4 w = modelMatrix * vec4(position, 1.0); vW = w.xyz; vN = normalize(mat3(modelMatrix) * normal); vTag = aTag;
        gl_Position = projectionMatrix * viewMatrix * w; }`,
    fragmentShader: `${PROJ_HEAD}
      uniform sampler2D uDepth; uniform float uFar, uExpo, uDebug, uRs; uniform vec3 uBaseCol;
      varying vec3 vW, vN; varying float vTag;
      float unpackDepth(vec4 c){ return dot(c, vec4(1.0, 1.0 / 255.0, 1.0 / 65025.0, 1.0 / 16581375.0)); }
      bool seen(vec3 P, vec3 N, out vec3 col){
        vec2 uv; float zf;
        if (!proj(P, uv, zf)) return false;
        if (dot(N, normalize(uPos - P)) <= 0.18) return false;      /* facing away, or seen so obliquely it would stretch */
        float dz = unpackDepth(texture2D(uDepth, uv)) * uFar;
        if (zf > dz + 0.06 + zf * 0.004) return false;
        col = texture2D(uImg, uv).rgb; return true;
      }
      void main(){
        vec3 col = uBaseCol, c;
        float az = atan(vW.z, vW.x);
        float s = floor(az / 0.7853982 + 0.5);
        float k = abs(s) <= 1.0 ? 0.0 : abs(s) >= 4.0 ? 3.1415927 : -sign(s) * (abs(s) - 1.0) * 0.7853982;
        if (vTag > 9.5 && vTag < 16.5) {      /* a pier and all that stands on it take one place in the photograph: the pier the
                                                 photograph sees from in front, so a statue is never two statues halved */
          float pk = floor((az - 0.3926991) / 0.7853982 + 0.5);
          k = pk >= 0.0 ? -pk * 0.7853982 : -(1.0 + pk) * 0.7853982;
        }
        bool ok = false; vec3 dbg = vec3(1.0, 0.0, 1.0);
        if (seen(rotY(vW, k), rotY(vN, k), c)) { col = c; ok = true; dbg = k == 0.0 ? vec3(0.0, 1.0, 0.0) : vec3(0.0, 0.6, 1.0); }
        if (!ok && vTag > 5.5) {      /* the room is the same either side of each pier: the same place mirrored across the
                                         nearest pier (behind a statue, round the end of a pier), in a bay the photograph sees */
          float pa = floor((az - 0.3926991) / 0.7853982 + 0.5) * 0.7853982 + 0.3926991;
          vec2 dd = vec2(cos(pa), sin(pa)), mxz = 2.0 * dot(vW.xz, dd) * dd - vW.xz, nxz = 2.0 * dot(vN.xz, dd) * dd - vN.xz;
          vec3 Mw = vec3(mxz.x, vW.y, mxz.y), Mn = vec3(nxz.x, vN.y, nxz.y);
          float ms = floor(atan(Mw.z, Mw.x) / 0.7853982 + 0.5);
          float mk = abs(ms) <= 1.0 ? 0.0 : abs(ms) >= 4.0 ? 3.1415927 : -sign(ms) * (abs(ms) - 1.0) * 0.7853982;
          if (vTag > 9.5 && vTag < 16.5) mk = k;
          if (seen(rotY(Mw, mk), rotY(Mn, mk), c)) { col = c; ok = true; dbg = vec3(0.85, 0.85, 0.85); }
        }
        if (!ok) for (int i = 0; i < 4; i++) {
          float a = (i == 0 ? 0.7853982 : i == 1 ? -0.7853982 : i == 2 ? 1.5707963 : -1.5707963) + k;
          if (seen(rotY(vW, a), rotY(vN, a), c)) { col = c; ok = true; dbg = vec3(1.0, 0.5, 0.0); break; }
        }
        if (!ok && vTag > 1.5 && vTag < 4.5) {
          float ba = floor(az / 0.7853982 + 0.5) * 0.7853982;
          vec3 n = vec3(cos(ba), 0.0, sin(ba)), d = vW - cameraPosition;
          float den = dot(d, n);
          if (abs(den) > 1e-4) {
            vec3 Q = cameraPosition + d * ((uRs - dot(cameraPosition, n)) / den);
            vec2 uv; float zf;
            for (int i = 0; i < 5; i++) {
              float a = i == 0 ? k : i == 1 ? k + 0.7853982 : i == 2 ? k - 0.7853982 : i == 3 ? k + 1.5707963 : k - 1.5707963;
              if (proj(rotY(Q, a), uv, zf)) { col = texture2D(uImg, uv).rgb; ok = true; dbg = vec3(1.0, 1.0, 0.0); break; }
            }
          }
        }
        if (!ok) for (int i = 0; i < 5; i++) {      /* last of all: the photograph's colour at the same place in some bay, unchecked */
          float a = i == 0 ? k : i == 1 ? k + 0.7853982 : i == 2 ? k - 0.7853982 : i == 3 ? k + 1.5707963 : k - 1.5707963;
          vec2 uv; float zf;
          if (proj(rotY(vW, a), uv, zf)) { col = texture2D(uImg, uv).rgb; ok = true; dbg = vec3(0.6, 0.2, 1.0); break; }
        }
        if (!ok) col = uBaseCol * (0.6 + 0.4 * max(0.0, vN.y));
        if (vW.y < 1.15 && (vTag < 1.5 || vTag > 9.5)) {          // the screens' and piers' low marble base: dark, veined, a lighter cap
          float g = 0.5 + 0.5 * sin(vW.x * 7.0 + vW.z * 5.0 + sin(vW.y * 23.0 + vW.x * 3.0) * 1.7);
          float g2 = 0.5 + 0.5 * sin(vW.x * 19.0 - vW.z * 13.0 + sin(vW.y * 41.0 + vW.z * 7.0) * 2.3);
          vec3 marble = uBaseCol * (0.7 + 0.45 * g + 0.25 * g2 * g2) * mix(1.0, 1.6, smoothstep(1.0, 1.13, vW.y));
          col = mix(col, marble, smoothstep(1.15, 1.02, vW.y));
        }
        if (uDebug > 0.5 && !ok) col = vec3(1.0, 0.0, 1.0);
        if (uDebug > 1.5) col = mix(col, dbg, 0.55);
        gl_FragColor = vec4(col * uExpo, 1.0);
        #include <colorspace_fragment>
      }`,
    side: THREE.DoubleSide});
}
/* The dome takes the photograph made below it; the dome repeats every 45 degrees, so where the frame ends the same place
   in the next compartment is used */
function domeMaterial(tex, k, U){
  return new THREE.ShaderMaterial({
    uniforms: Object.assign(photoUniforms(PHOTO.dome, tex, k), {uExpo: U.uExpo}),
    vertexShader: `varying vec3 vW; void main(){ vec4 w = modelMatrix * vec4(position, 1.0); vW = w.xyz; gl_Position = projectionMatrix * viewMatrix * w; }`,
    fragmentShader: `${PROJ_HEAD}
      uniform float uExpo; varying vec3 vW;
      void main(){
        vec2 uv, buv; float zf; vec3 col = vec3(0.55, 0.47, 0.33); float best = 1e9;
        for (int i = 0; i < 8; i++) {
          vec3 P = rotY(vW, float(i) * 0.7853982);
          if (proj(P, uv, zf)) {
            vec2 q = abs(uv - 0.5);
            float m = max(q.x * uW / uH, q.y) - (i == 0 ? 0.25 : 0.0);
            if (m < best) { best = m; buv = uv; }
          }
        }
        if (best < 1e8) col = texture2D(uImg, buv).rgb;
        gl_FragColor = vec4(col * uExpo, 1.0);
        #include <colorspace_fragment>
      }`,
    side: THREE.DoubleSide});
}
function depthMaterial(){
  return new THREE.ShaderMaterial({uniforms: {uPos: {value: V3()}, uF: {value: V3()}, uFar: {value: 120}},
    vertexShader: `varying vec3 vW; void main(){ vec4 w = modelMatrix * vec4(position, 1.0); vW = w.xyz; gl_Position = projectionMatrix * viewMatrix * w; }`,
    fragmentShader: `uniform vec3 uPos, uF; uniform float uFar; varying vec3 vW;
      vec4 packDepth(float v){ vec4 r = fract(v * vec4(1.0, 255.0, 65025.0, 16581375.0)); r -= r.yzww * vec4(1.0 / 255.0, 1.0 / 255.0, 1.0 / 255.0, 0.0); return r; }
      void main(){ gl_FragColor = packDepth(clamp(dot(vW - uPos, uF) / uFar, 0.0, 0.9999)); }`,
    side: THREE.DoubleSide});
}

/* ================================ pictures drawn here ================================ */
function drawn(w, h, draw){ const c = document.createElement("canvas"); c.width = w; c.height = h; draw(c.getContext("2d"), w, h); return c; }
function ctex(c, srgb = true){ const t = new THREE.CanvasTexture(c); if (srgb) t.colorSpace = THREE.SRGBColorSpace; t.anisotropy = 8; return t; }
function texOf(img, srgb, repeat){
  if (!img) return null;
  const t = new THREE.Texture(img); t.needsUpdate = true; if (srgb) t.colorSpace = THREE.SRGBColorSpace;
  if (typeof ImageBitmap !== "undefined" && img instanceof ImageBitmap) t.flipY = false;      // decoded already turned over
  if (repeat) t.wrapS = t.wrapT = THREE.RepeatWrapping;
  t.anisotropy = 8; return t;
}
/* the carpet: a pale grey-green field with a fine lattice of dots, and rosettes in staggered rows four feet apart (as the
   room's photographs show it); one tile is eight feet */
const CARPET_TILE = 8 * FT;
function carpetCanvas(lean){
  const S = lean ? 512 : 1024;
  return drawn(S, S, (g, w) => {
    const k = w / CARPET_TILE, R = rng(5);
    g.fillStyle = "#b4b7ac"; g.fillRect(0, 0, w, w);
    for (let i = 0; i < 9000 * (S / 1024) ** 2; i++) { g.fillStyle = R() < 0.5 ? "rgba(255,255,255,.07)" : "rgba(60,70,70,.07)"; g.fillRect(R() * w, R() * w, 2, 2); }
    const step = 0.06 * k;
    g.fillStyle = "#7d8784";
    for (let y = 0, row = 0; y < w + step; y += step, row++) for (let x = (row % 2) * step / 2; x < w + step; x += step) { g.beginPath(); g.arc(x, y, 0.0048 * k, 0, 7); g.fill(); }
    const rosette = (cx, cy) => {
      const r = 0.22 * k;
      g.save(); g.translate(cx, cy);
      g.fillStyle = "#b4b7ac"; g.beginPath(); g.arc(0, 0, r * 1.08, 0, 7); g.fill();
      g.strokeStyle = "#3a4558"; g.lineWidth = r * 0.05; g.beginPath(); g.arc(0, 0, r * 0.98, 0, 7); g.stroke();
      for (let i = 0; i < 24; i++) { g.save(); g.rotate(i * Math.PI / 12);
        g.fillStyle = i % 2 ? "#4a5468" : "#38425a"; g.beginPath(); g.moveTo(0, -r * 0.48); g.quadraticCurveTo(r * 0.12, -r * 0.7, 0, -r * 0.9); g.quadraticCurveTo(-r * 0.12, -r * 0.7, 0, -r * 0.48); g.fill(); g.restore(); }
      g.fillStyle = "#7f3d33"; g.beginPath(); g.arc(0, 0, r * 0.44, 0, 7); g.fill();
      g.fillStyle = "#b4b7ac";
      for (let i = 0; i < 8; i++) { g.save(); g.rotate(i * Math.PI / 4 + 0.2); g.beginPath(); g.ellipse(0, -r * 0.29, r * 0.05, r * 0.11, 0, 0, 7); g.fill(); g.restore(); }
      g.fillStyle = "#4b6a50"; g.beginPath(); g.arc(0, 0, r * 0.18, 0, 7); g.fill();
      g.fillStyle = "#cdbf98"; g.beginPath(); g.arc(0, 0, r * 0.07, 0, 7); g.fill();
      g.restore();
    };
    const a = w / 2;
    for (const [x, y] of [[0, 0], [a, 0], [w, 0], [0, w], [a, w], [w, w], [a / 2, a], [a * 1.5, a], [-a / 2, a], [w + a / 2, a]]) rosette(x + a / 2, y);
  });
}
/* the wreathed open book set into the carpet in the aisles */
function medallionCanvas(){
  return drawn(512, 512, (g, w) => {
    const c = w / 2, R = rng(9);
    g.translate(c, c);
    g.strokeStyle = "#2e5a3a"; g.lineWidth = 7;
    for (const s of [-1, 1]) {
      g.beginPath(); g.arc(0, 0, w * 0.4, Math.PI / 2 + s * 0.25, Math.PI / 2 + s * 2.9, s < 0); g.stroke();
      for (let i = 0; i < 22; i++) {
        const a = Math.PI / 2 + s * (0.35 + i * 0.118), x = Math.cos(a) * w * 0.4, y = Math.sin(a) * w * 0.4;
        for (const o of [-1, 1]) { g.save(); g.translate(x, y); g.rotate(a + s * Math.PI / 2 + o * 0.55); g.fillStyle = i % 3 ? "#356b42" : "#2b5636";
          g.beginPath(); g.ellipse(0, -14, 6, 16, 0, 0, 7); g.fill(); g.restore(); }
        if (i % 4 === 2) { g.fillStyle = "#8e3b31"; g.beginPath(); g.arc(x * 1.06, y * 1.06, 4, 0, 7); g.fill(); }
      }
    }
    g.save(); g.scale(1, 0.92);
    for (const s of [-1, 1]) {
      g.fillStyle = "#d9c9a2"; g.strokeStyle = "#5b4630"; g.lineWidth = 3;
      g.beginPath(); g.moveTo(0, -78); g.quadraticCurveTo(s * 60, -96, s * 118, -84); g.lineTo(s * 118, 74); g.quadraticCurveTo(s * 60, 62, 0, 82); g.closePath(); g.fill(); g.stroke();
      g.fillStyle = "#6b5a44";
      for (let l = 0; l < 13; l++) { const y = -62 + l * 10.5, x0 = s * 16, x1 = s * (100 - (l === 12 ? 30 : 0)); g.fillRect(Math.min(x0, x1), y, Math.abs(x1 - x0) * (0.85 + 0.15 * R()), 3); }
    }
    g.restore();
  });
}
/* the spines on the reference shelves: two shelves of bound books, a little over a metre of them */
function spinesCanvas(lean){
  return drawn(lean ? 512 : 1024, lean ? 256 : 512, (g, w, h) => {
    const R = rng(21), cols = ["#6e1f1a", "#7a2a1e", "#5a1814", "#3b2a1f", "#4b3424", "#23323f", "#2c3b2c", "#7d5a32", "#8a3b22", "#5c2433", "#1f2a33"];
    g.fillStyle = "#1b120d"; g.fillRect(0, 0, w, h);
    for (const [y0, y1] of [[0.04, 0.47], [0.53, 0.96]]) {
      let x = 0;
      while (x < w) {
        const bw = (0.022 + R() * 0.035) * w / 1.2, hh = (0.72 + R() * 0.26) * (y1 - y0) * h, base = y1 * h;
        const c = cols[(R() * cols.length) | 0];
        g.fillStyle = c; g.fillRect(x, base - hh, bw - 1, hh);
        const gr = g.createLinearGradient(x, 0, x + bw, 0); gr.addColorStop(0, "rgba(0,0,0,.35)"); gr.addColorStop(0.35, "rgba(255,255,255,.08)"); gr.addColorStop(1, "rgba(0,0,0,.4)");
        g.fillStyle = gr; g.fillRect(x, base - hh, bw - 1, hh);
        g.fillStyle = "rgba(214,178,98,.75)";
        for (const f of [0.12, 0.2, 0.8]) g.fillRect(x + 1, base - hh * (1 - f), bw - 3, Math.max(1, h * 0.004));
        if (R() < 0.6) { g.fillStyle = "rgba(200,170,110,.55)"; g.fillRect(x + bw * 0.2, base - hh * 0.7, bw * 0.55, hh * 0.12); }
        x += bw;
      }
      g.fillStyle = "#2a1a12"; g.fillRect(0, y1 * h, w, 0.06 * h);
    }
  });
}

/* ================================ the record itself: its pages ================================ */
const SERIF = "'Times New Roman', Times, 'Liberation Serif', 'Noto Serif', Georgia, serif";
/* Text of the kind every day's proceedings carry, without names or dates: the standing forms of the House's opening, its
   journal, the pledge, messages, and the referral of communications and bills. */
const PROSE = [
  ["h", "HOUSE OF REPRESENTATIVES"],
  ["p", "The House met at noon and was called to order by the Speaker pro tempore."],
  ["h", "THE JOURNAL"],
  ["p", "The SPEAKER pro tempore. The Chair has examined the Journal of the last day's proceedings and announces to the House the approval thereof."],
  ["p", "Pursuant to clause 1, rule I, the Journal stands approved."],
  ["h", "PLEDGE OF ALLEGIANCE"],
  ["p", "The SPEAKER pro tempore. The Member designated by the Chair will come forward and lead the House in the Pledge of Allegiance."],
  ["p", "I pledge allegiance to the Flag of the United States of America, and to the Republic for which it stands, one nation under God, indivisible, with liberty and justice for all."],
  ["h", "MESSAGE FROM THE SENATE"],
  ["p", "A message from the Senate by one of its clerks announced that the Senate has passed without amendment a bill of the House of the following title, and that the Senate has passed bills of the following titles in which the concurrence of the House is requested."],
  ["h", "ANNOUNCEMENT BY THE SPEAKER PRO TEMPORE"],
  ["p", "The SPEAKER pro tempore. The Chair will entertain requests for one-minute speeches on each side of the aisle."],
  ["h", "COMMUNICATION FROM THE CLERK OF THE HOUSE"],
  ["p", "The SPEAKER pro tempore laid before the House the following communication from the Clerk of the House of Representatives, which was read and, without objection, ordered to be printed."],
  ["h", "ENROLLED BILLS SIGNED"],
  ["p", "The Clerk reported and found truly enrolled bills of the House of the following titles, which were thereupon signed by the Speaker."],
  ["h", "LEAVE OF ABSENCE"],
  ["p", "By unanimous consent, leave of absence was granted to Members as requested, on account of official business in their districts."],
  ["h", "EXECUTIVE COMMUNICATIONS, ETC."],
  ["p", "Under clause 2 of rule XIV, executive communications were taken from the Speaker's table and referred as follows:"],
  ["p", "A letter from the Secretary of Agriculture, transmitting the Department's report on the conservation programs administered in the preceding fiscal year; to the Committee on Agriculture."],
  ["p", "A letter from the Comptroller General of the United States, transmitting a report on the management of federal grant programs; to the Committee on Appropriations."],
  ["p", "A letter from the Secretary of the Interior, transmitting the annual report on the condition of the national park system; to the Committee on Natural Resources."],
  ["p", "A letter from the Secretary of Transportation, transmitting the biennial report on the condition and performance of the nation's highways, bridges and transit; to the Committee on Transportation and Infrastructure."],
  ["h", "REPORTS OF COMMITTEES ON PUBLIC BILLS AND RESOLUTIONS"],
  ["p", "Under clause 2 of rule XIII, reports of committees were delivered to the Clerk for printing and reference to the proper calendar, as follows:"],
  ["p", "Committee on Rules. Report on the resolution providing for consideration of the bill making appropriations for the fiscal year, and for other purposes; referred to the House Calendar and ordered to be printed."],
  ["h", "PUBLIC BILLS AND RESOLUTIONS"],
  ["p", "Under clause 2 of rule XII, public bills and resolutions of the following titles were introduced and severally referred, as follows:"],
  ["p", "A bill to amend title 38, United States Code, to improve the provision of care to veterans in rural areas, and for other purposes; to the Committee on Veterans' Affairs."],
  ["p", "A bill to authorize appropriations for the national weather service for the next five fiscal years, and for other purposes; to the Committee on Science, Space, and Technology."],
  ["p", "A bill to provide for the preservation and public display of the historic collections of the Library of Congress, and for other purposes; to the Committee on House Administration."],
  ["p", "A joint resolution proposing an amendment to the Constitution of the United States; to the Committee on the Judiciary."],
  ["h", "ADJOURNMENT"],
  ["p", "The SPEAKER pro tempore. Without objection, the House stands adjourned until tomorrow at noon for morning-hour debate."]
];
/* one page: the running head, the page number and three columns of text set in the record's manner */
function drawPage(g, w, h, o){
  g.fillStyle = "#f3eee2"; g.fillRect(0, 0, w, h);
  const R = rng(o.seed || 1);
  for (let i = 0; i < w * h / 900; i++) { g.fillStyle = R() < 0.5 ? "rgba(120,100,60,.035)" : "rgba(255,255,255,.05)"; g.fillRect(R() * w, R() * h, 2, 2); }      // the paper's fibre
  const m = w * 0.075, top = h * 0.07, colGap = w * 0.022, ncol = 3, colW = (w - 2 * m - colGap * (ncol - 1)) / ncol;
  const fs = w * 0.0172, lh = fs * 1.16, ink = "#1d1a17";
  g.fillStyle = ink; g.textBaseline = "alphabetic";
  let y0 = top;
  /* the running head: page number outside, the title in the middle */
  g.font = `600 ${fs * 1.02}px ${SERIF}`;
  const head = "CONGRESSIONAL RECORD — HOUSE", hw = g.measureText(head).width;
  g.fillText(head, (w - hw) / 2, y0);
  g.font = `700 ${fs * 1.02}px ${SERIF}`;
  const pn = "H" + o.page, pw = g.measureText(pn).width;
  g.fillText(pn, o.left ? m : w - m - pw, y0);
  g.fillRect(m, y0 + fs * 0.45, w - 2 * m, Math.max(1, h * 0.0012));
  y0 += fs * 1.6;
  let k = o.start || 0, para = null, words = [], wi = 0;
  const next = () => { para = PROSE[k % PROSE.length]; k++; words = para[1].split(" "); wi = 0; };
  next();
  for (let c = 0; c < ncol; c++) {
    const x0 = m + c * (colW + colGap);
    let y = y0 + fs;
    if (c > 0) g.fillRect(x0 - colGap / 2, y0, Math.max(1, w * 0.0008), h - y0 - h * 0.06);
    while (y < h - h * 0.06) {
      if (para[0] === "h") {      // a heading, centred in the column, with a little space round it
        g.font = `700 ${fs * 0.96}px ${SERIF}`;
        const lines = [], ws = para[1].split(" "); let line = "";
        for (const t of ws) { const tryL = line ? line + " " + t : t; if (g.measureText(tryL).width > colW && line) { lines.push(line); line = t; } else line = tryL; }
        lines.push(line);
        y += lh * 0.5;
        for (const L of lines) { const lw = g.measureText(L).width; g.fillText(L, x0 + (colW - lw) / 2, y); y += lh; }
        y += lh * 0.3; next(); continue;
      }
      /* a paragraph, justified, its first line indented */
      g.font = `400 ${fs}px ${SERIF}`;
      const indent = wi === 0 ? fs * 1.2 : 0, line = [];
      let lw = 0;
      while (wi < words.length) {
        const ww = g.measureText(words[wi]).width, sp = line.length ? g.measureText(" ").width : 0;
        if (lw + sp + ww > colW - indent && line.length) break;
        line.push(words[wi]); lw += sp + ww; wi++;
      }
      const end = wi >= words.length;
      if (line.length > 1 && !end) {
        const gap = (colW - indent - line.reduce((s, t) => s + g.measureText(t).width, 0)) / (line.length - 1);
        let x = x0 + indent;
        for (const t of line) { g.fillText(t, x, y); x += g.measureText(t).width + gap; }
      } else g.fillText(line.join(" "), x0 + indent, y);
      y += lh;
      if (end) next();
    }
  }
  /* the faint grey of a page's edge where the leaves are cut, and the gutter's shadow */
  const gr = g.createLinearGradient(o.left ? w : 0, 0, o.left ? w * 0.86 : w * 0.14, 0);
  gr.addColorStop(0, "rgba(70,55,35,.28)"); gr.addColorStop(1, "rgba(70,55,35,0)");
  g.fillStyle = gr; g.fillRect(0, 0, w, h);
}
function pageCanvas(o, lean){ const w = lean || o.brief ? 512 : 768; return drawn(w, Math.round(w * 1.349), (g, W, H) => drawPage(g, W, H, o)); }
/* the spread it falls open at, the three leaves turned, the spread it ends on: left (even) and right (odd) pages */
const P0 = 4316;
const PAGES = {L0: {page: P0, left: true, start: 3}, R0: {page: P0 + 1, start: 11}, L1: {page: P0 + 2, left: true, start: 15, brief: 1}, R1: {page: P0 + 3, start: 19, brief: 1},
               L2: {page: P0 + 4, left: true, start: 22, brief: 1}, R2: {page: P0 + 5, start: 26, brief: 1}, L3: {page: P0 + 6, left: true, start: 29}, R3: {page: P0 + 7, start: 0}};
for (const o of Object.values(PAGES)) o.seed = o.page;
/* the cover: the leather, a blind-tooled double rule, and the title in gold; returns its colour and its rough/metal maps */
function coverCanvases(leatherImg, lean){
  const W = lean ? 512 : 1024, H = Math.round(W * 1.335);
  const mask = document.createElement("canvas"); mask.width = W; mask.height = H;
  const mg = mask.getContext("2d");
  mg.clearRect(0, 0, W, H); mg.fillStyle = "#fff"; mg.strokeStyle = "#fff";
  mg.textAlign = "center"; mg.textBaseline = "middle";
  mg.font = `700 ${W * 0.072}px ${SERIF}`;
  mg.fillText("CONGRESSIONAL", W / 2, H * 0.3); mg.fillText("RECORD", W / 2, H * 0.3 + W * 0.1);
  mg.lineWidth = W * 0.004; for (const y of [H * 0.24, H * 0.42]) { mg.beginPath(); mg.moveTo(W * 0.3, y); mg.lineTo(W * 0.7, y); mg.stroke(); }
  const map = drawn(W, H, (g) => {
    if (leatherImg) { const s = W * 0.4 / 0.223; for (let y = 0; y < H; y += s) for (let x = 0; x < W; x += s) g.drawImage(leatherImg, x, y, s, s); }      // the photographed leather is 0.4 m across
    else { g.fillStyle = "#5a2a1e"; g.fillRect(0, 0, W, H); }
    g.globalCompositeOperation = "multiply"; g.fillStyle = "#b46a52"; g.fillRect(0, 0, W, H); g.globalCompositeOperation = "source-over";
    g.strokeStyle = "rgba(20,8,4,.55)"; g.lineWidth = W * 0.006;
    for (const k of [0.05, 0.065]) g.strokeRect(W * k, H * k * 0.75, W * (1 - 2 * k), H * (1 - 1.5 * k));
    const gold = g.createLinearGradient(0, H * 0.24, 0, H * 0.42); gold.addColorStop(0, "#e8c773"); gold.addColorStop(0.5, "#b88a3a"); gold.addColorStop(1, "#e2bd66");
    const tmp = document.createElement("canvas"); tmp.width = W; tmp.height = H; const tg = tmp.getContext("2d");
    tg.fillStyle = gold; tg.fillRect(0, 0, W, H); tg.globalCompositeOperation = "destination-in"; tg.drawImage(mask, 0, 0);
    g.drawImage(tmp, 0, 0);
  });
  /* roughness in green, metal in blue: the leather dull, the gold bright and metallic */
  const orm = drawn(W, H, (g) => {
    const m = mg.getImageData(0, 0, W, H).data, out = g.createImageData(W, H), o = out.data;
    for (let i = 0; i < m.length; i += 4) { const k = m[i + 3] / 255; o[i] = 255; o[i + 1] = 158 - 90 * k; o[i + 2] = 255 * k; o[i + 3] = 255; }
    g.putImageData(out, 0, 0); });
  return {map, orm};
}
/* The wear on the desks' tops (John, 2026-10-11: "real wear and imperfection"): the varnish dulled where elbows and
   books have rested, fine scratches along the grain, a ring or two where a cup once stood. Grey: how rough the finish
   is there, over the wood's own map; one tile is 1.2 by 1.2 metres. */
function wearCanvas(lean){
  const S = lean ? 256 : 512;
  return drawn(S, S, (g, w) => {
    const R = rng(77);
    g.fillStyle = "#808080"; g.fillRect(0, 0, w, w);
    for (let i = 0; i < 14; i++) {      // dulled patches, soft-edged
      const x = R() * w, y = R() * w, rx = (0.08 + R() * 0.2) * w, ry = rx * (0.4 + R() * 0.5);
      const gr = g.createRadialGradient(x, y, 0, x, y, rx); gr.addColorStop(0, `rgba(255,255,255,${0.1 + R() * 0.18})`); gr.addColorStop(1, "rgba(255,255,255,0)");
      g.save(); g.translate(x, y); g.scale(1, ry / rx); g.translate(-x, -y); g.fillStyle = gr; g.beginPath(); g.arc(x, y, rx, 0, 7); g.fill(); g.restore();
    }
    for (let i = 0; i < (lean ? 90 : 220); i++) {      // scratches, mostly along the grain
      const x = R() * w, y = R() * w, L = (0.02 + R() * 0.16) * w, a = (R() - 0.5) * 0.12 + (R() < 0.12 ? (R() - 0.5) * 1.6 : 0);
      g.strokeStyle = `rgba(255,255,255,${0.08 + R() * 0.25})`; g.lineWidth = R() < 0.8 ? 1 : 1.6;
      g.beginPath(); g.moveTo(x, y); g.lineTo(x + Math.cos(a) * L, y + Math.sin(a) * L); g.stroke();
    }
    for (let i = 0; i < 3; i++) {      // rings
      const x = R() * w, y = R() * w, r = (0.03 + R() * 0.02) * w;
      g.strokeStyle = `rgba(255,255,255,${0.1 + R() * 0.12})`; g.lineWidth = 1.5 + R() * 1.5; g.beginPath(); g.arc(x, y, r, R() * 2, R() * 2 + 3.5 + R() * 2.5); g.stroke();
    }
    g.globalAlpha = 0.5;      // the grain's own gloss varies a little
    for (let i = 0; i < 2000 * (S / 512) ** 2; i++) { g.fillStyle = R() < 0.5 ? "rgba(255,255,255,.06)" : "rgba(0,0,0,.06)"; g.fillRect(R() * w, R() * w, 1 + R() * 3, 1); }
  });
}
/* the page block's cut edges: fine lines of paper */
function edgesCanvas(){
  return drawn(64, 512, (g, w, h) => {
    g.fillStyle = "#e7dfcd"; g.fillRect(0, 0, w, h);
    const R = rng(4);
    for (let y = 0; y < h; y += 2) { g.fillStyle = `rgba(110,95,70,${0.05 + R() * 0.12})`; g.fillRect(0, y, w, 1); }
  });
}

/* ================================ the furniture ================================ */
function wood(A, lean, opts = {}){
  /* opts.tint: a CSS colour, or a THREE.Color in linear light (it may go above 1: the photographed wood is a very dark
     mahogany, and the room's desks are polished red-brown under a bright dome) */
  const tint = opts.tint && opts.tint.isColor ? opts.tint : new THREE.Color(opts.tint || "#c9a593");
  const [dImg, nImg, rImg] = A.wood, m = new THREE.MeshPhysicalMaterial({color: tint, roughness: opts.rough ?? 0.42, clearcoat: opts.coat ?? 0.35, clearcoatRoughness: 0.12});
  if (dImg) { m.map = texOf(dImg, true, true); m.map.repeat.set(1 / 0.6, 1 / 0.6); }
  if (nImg) { m.normalMap = texOf(nImg, false, true); m.normalMap.repeat.set(1 / 0.6, 1 / 0.6); m.normalScale.set(0.35, 0.35); }
  if (rImg) { m.roughnessMap = texOf(rImg, false, true); m.roughnessMap.repeat.set(1 / 0.6, 1 / 0.6); m.roughness = (opts.rough ?? 0.42) * 1.6; }      // the map's grey is about 0.6
  /* the wear (opts.wear, a canvas): the finish dulled and scratched here and there, over the wood's own roughness, and
     the clearcoat thinned where it is worn */
  if (opts.wear) {
    const wt = ctex(opts.wear, false); wt.wrapS = wt.wrapT = THREE.RepeatWrapping; wt.repeat.set(1 / 1.2, 1 / 1.2);
    m.userData.wear = wt;
    const prev = m.onBeforeCompile;
    m.onBeforeCompile = (sh, r) => {
      if (prev) prev(sh, r);
      sh.uniforms.uWear = {value: wt};
      sh.vertexShader = sh.vertexShader.replace("#include <common>", "#include <common>\nvarying vec3 vWearP;")
        .replace("#include <worldpos_vertex>", "#include <worldpos_vertex>\n#ifdef USE_INSTANCING\nvWearP = (modelMatrix * instanceMatrix * vec4(transformed, 1.0)).xyz;\n#else\nvWearP = (modelMatrix * vec4(transformed, 1.0)).xyz;\n#endif");
      sh.fragmentShader = sh.fragmentShader.replace("#include <common>", "#include <common>\nvarying vec3 vWearP; uniform sampler2D uWear;")
        .replace("#include <roughnessmap_fragment>", `#include <roughnessmap_fragment>
        float wearK = texture2D(uWear, vWearP.xz * 0.8333 + vWearP.y * 0.37).r - 0.5;
        roughnessFactor = clamp(roughnessFactor + wearK * 0.9, 0.05, 1.0);`)
        .replace("#include <lights_physical_fragment>", `#include <lights_physical_fragment>
        material.clearcoatRoughness = clamp(material.clearcoatRoughness + max(wearK, 0.0) * 0.6, 0.0, 1.0);`);
    };
    tagged(m, "wear");
  }
  return m;
}
/* the light of every desk lamp but yours on the desks round it: each lamp is a warm light under its hood, worked out in the
   desks' own shader from where the lamps stand (a lamp to every four feet along each ring), so a hundred lamps cost
   nothing more than one */
function tagged(mat, tag){ const t = (mat.userData.chain = (mat.userData.chain || []).concat(tag)).join("+"); mat.customProgramCacheKey = () => t; }
function lampPools(mat, U){
  tagged(mat, "lampPools");
  const prev = mat.onBeforeCompile;
  mat.onBeforeCompile = (sh, r) => {
    if (prev) prev(sh, r);
    sh.uniforms.uLampI = U.uLampI; sh.uniforms.uHeroAz = U.uHeroAz; sh.uniforms.uSunI = U.uSunI; sh.uniforms.uBeamA = U.uBeamA; sh.uniforms.uBeamD = U.uBeamD; sh.uniforms.uBeamP = U.uBeamP; sh.uniforms.uNBeam = U.uNBeam;
    sh.vertexShader = sh.vertexShader.replace("#include <common>", "#include <common>\nvarying vec3 vWp;")
      .replace("#include <worldpos_vertex>", "#include <worldpos_vertex>\n#ifdef USE_INSTANCING\nvWp = (modelMatrix * instanceMatrix * vec4(transformed, 1.0)).xyz;\n#else\nvWp = (modelMatrix * vec4(transformed, 1.0)).xyz;\n#endif");
    sh.fragmentShader = sh.fragmentShader.replace("#include <common>", `#include <common>
      varying vec3 vWp; uniform float uLampI, uHeroAz, uSunI; uniform vec3 uBeamA[4], uBeamD[4]; uniform vec4 uBeamP[4]; uniform int uNBeam;
      ${BEAM_PROF_GLSL}
      /* the sun where a shaft lands: on the carpet and the desks it crosses, a warm pool the width of the shaft, the window's
         bars and panes drawn in it */
      vec3 sunLight(vec3 P, vec3 N){
        vec3 acc = vec3(0.0);
        for (int i = 0; i < 4; i++) {
          if (i >= uNBeam) break;
          vec3 w = P - uBeamA[i]; float s = dot(w, uBeamD[i]);
          if (s < 0.0 || s > uBeamP[i].y) continue;
          vec3 q = w - s * uBeamD[i]; float d = length(q) / uBeamP[i].x;
          vec3 tb, bb; beamAxes(uBeamD[i], tb, bb);
          float k = beamProf(d, dot(q, tb), dot(q, bb), uBeamP[i].w) * max(dot(N, -uBeamD[i]), 0.0);
          acc += vec3(1.0, 0.86, 0.66) * k * uBeamP[i].z * 1.3;
        }
        return acc * uSunI;
      }
      vec3 lampLight(vec3 P, vec3 N){
        float r = length(P.xz), a = atan(P.z, P.x);
        vec3 acc = vec3(0.0);
        for (int ri = 0; ri < 3; ri++) {
          float rc = ri == 0 ? ${LAY.rings[0].rc.toFixed(4)} : ri == 1 ? ${LAY.rings[1].rc.toFixed(4)} : ${LAY.rings[2].rc.toFixed(4)};
          if (abs(r - rc) > 1.6) continue;
          float stp = ${LAY.lampStep.toFixed(4)} / rc, hfa = 0.3926991 - atan(${(LAY.aisle / 2).toFixed(4)} / rc);
          float sc = floor((a - 0.3926991) / 0.7853982 + 0.5) * 0.7853982 + 0.3926991;
          float n = floor((hfa * rc - 0.45) / ${LAY.lampStep.toFixed(4)});
          float j0 = clamp(floor((a - sc) / stp + 0.5), -n, n);
          for (int dj = -1; dj <= 1; dj++) {
            float j = j0 + float(dj);
            if (abs(j) > n) continue;
            float la = sc + j * stp;
            if (ri == 1 && abs(la - uHeroAz) < 0.002) continue;
            vec3 L = vec3(rc * cos(la), ${(LAY.hoodY - 0.01).toFixed(3)}, rc * sin(la)) - P;
            float d2 = dot(L, L); L *= inversesqrt(d2);
            float down = clamp(-L.y, 0.0, 1.0);
            acc += vec3(1.0, 0.78, 0.52) * max(dot(N, L), 0.0) * smoothstep(0.08, 0.5, down) / max(d2, 0.04);
          }
        }
        return acc * uLampI;
      }`).replace("#include <lights_fragment_end>", `#include <lights_fragment_end>
      { vec3 wN = inverseTransformDirection(normal, viewMatrix);
        float ground = mix(0.56, 1.0, smoothstep(0.0, 0.72, vWp.y)) * mix(0.82, 1.0, 0.5 + 0.5 * wN.y);      // less of the room's light low down and on faces that look down
        reflectedLight.indirectDiffuse *= ground; reflectedLight.indirectSpecular *= mix(0.7, 1.0, ground);
        reflectedLight.directDiffuse += diffuseColor.rgb * (lampLight(vWp, wN) + sunLight(vWp, wN)); }`);
  };
}
/* The glass on the desks reflects the room crisply, but a reading lamp's tube, hidden in its hood, shows in the glass as
   a soft glow, not the point of light a point light would leave: the only direct light is your lamp, so its share of the
   glass's reflection is turned down here, and the room's (from its photographs) is kept */
function softGlint(mat, k){
  const prev = mat.onBeforeCompile;
  mat.onBeforeCompile = (sh, r) => {
    if (prev) prev(sh, r);
    sh.fragmentShader = sh.fragmentShader.replace("( clearcoatSpecularDirect + clearcoatSpecularIndirect ) * material.clearcoat",
      "( clearcoatSpecularDirect * " + k.toFixed(3) + " + clearcoatSpecularIndirect ) * material.clearcoat");
  };
  tagged(mat, "softGlint" + k);
}
/* the carpet in the shade under the desks: darker where a desk's top or a chair covers it */
function underDesks(mat){
  tagged(mat, "underDesks");
  const prev = mat.onBeforeCompile;
  mat.onBeforeCompile = (sh, r) => {
    if (prev) prev(sh, r);
    sh.fragmentShader = sh.fragmentShader.replace("#include <map_fragment>", `#include <map_fragment>
      {
        float r = length(vWp.xz), a = atan(vWp.z, vWp.x), shade = 1.0;
        for (int ri = 1; ri < 3; ri++) {
          float rc = ri == 1 ? ${LAY.rings[1].rc.toFixed(4)} : ${LAY.rings[2].rc.toFixed(4)};
          float hfa = 0.3926991 - atan(${(LAY.aisle / 2).toFixed(4)} / rc);
          float sc = floor((a - 0.3926991) / 0.7853982 + 0.5) * 0.7853982 + 0.3926991;
          float da = abs(a - sc) * r;
          float inR = smoothstep(${(LAY.hw + LAY.depth + 0.12).toFixed(3)}, ${(LAY.hw + LAY.depth - 0.25).toFixed(3)}, abs(r - rc));
          float inA = smoothstep(hfa * rc + 0.1, hfa * rc - 0.2, da);
          shade = min(shade, 1.0 - 0.62 * inR * inA * (0.75 + 0.25 * smoothstep(0.7, 0.0, abs(r - rc))));
        }
        float cd = smoothstep(4.75, 4.42, r);
        shade = min(shade, 1.0 - 0.45 * cd);
        diffuseColor.rgb *= shade;
      }`);
  };
}
/* a ring of double-faced desks (or, for the reference ring, low bookcases with sloping tops), as merged geometry */
function deskRings(){
  const wood = new Mesher(), tops = new Mesher(), glass = new Mesher(), books = new Mesher(), lamps = [];
  for (let ri = 0; ri < LAY.rings.length; ri++) {
    const {rc, kind} = LAY.rings[ri], step = LAY.lampStep / rc, half = 22.5 * D2R - Math.atan(LAY.aisle / 2 / rc);
    const n = Math.floor((half * rc - 0.45) / LAY.lampStep);
    for (let s = 0; s < 8; s++) {
      const sc = (22.5 + 45 * s) * D2R, a0 = sc - half, a1 = sc + half, segs = Math.max(8, Math.round(half * 2 * rc / 0.25));
      for (let j = -n; j <= n; j++) lamps.push({ri, a: sc + j * step, rc});
      if (kind === "ref") {
        const w = 0.31;
        sweep(wood, [[rc - w - 0.02, 0], [rc + w + 0.02, 0], [rc + w + 0.02, 0.09], [rc - w - 0.02, 0.09]], a0, a1, segs, true, true);
        sweep(wood, [[rc - w, 0.09], [rc + w, 0.09], [rc + w, 0.9], [rc + 0.05, 1.02], [rc - 0.05, 1.02], [rc - w, 0.9]], a0, a1, segs, true, true);
        for (const sgn of [-1, 1]) {      // the shelves of books on both faces, and the lip of the sloping top
          const rf = rc + sgn * (w + 0.002), face2 = [[rf, 0.12], [rf, 0.86]];
          sweep(books, sgn > 0 ? face2 : face2.reverse(), a0 + 0.012, a1 - 0.012, segs, false);
          sweep(wood, rect(Math.min(rc + sgn * (w + 0.035), rc + sgn * w), Math.max(rc + sgn * (w + 0.035), rc + sgn * w), 0.875, 0.915), a0, a1, segs, true, false);
        }
        sweep(wood, [[rc - 0.06, 1.02], [rc + 0.06, 1.02], [rc + 0.06, 1.1], [rc - 0.06, 1.1]], a0, a1, segs, true, true);
        continue;
      }
      const hw = LAY.hw, D = LAY.depth, ro = rc + hw + D, rin = rc - hw - D, T = LAY.top, SP = LAY.spine;
      sweep(wood, [[rc - 0.16, 0], [rc + 0.16, 0], [rc + 0.16, 0.1], [rc - 0.16, 0.1]], a0, a1, segs, true, true);                 // the plinth
      sweep(wood, [[rc - hw, 0.1], [rc + hw, 0.1], [rc + hw, SP - 0.03], [rc + hw - 0.012, SP - 0.008], [rc, SP], [rc - hw + 0.012, SP - 0.008], [rc - hw, SP - 0.03]], a0, a1, segs, true, true);      // the spine
      for (const [r0, r1, sg] of [[rc + hw, ro, 1], [rin, rc - hw, -1]]) {
        const edge = sg > 0 ? r1 : r0, G = LAY.glass;
        /* the top, its front edge rounded, and the plate glass laid on it, whose cut edge shows green */
        sweep(wood, sg > 0 ? [[r0, T - 0.04], [r1, T - 0.04], [r1 + 0.005, T - 0.02], [r1, T], [r0, T]] : [[r0, T - 0.04], [r1, T - 0.04], [r1, T], [r0, T], [r0 - 0.005, T - 0.02]], a0, a1, segs, true, true);
        sweep(tops, [[r1 - (sg > 0 ? 0.003 : 0.004), T + G], [r0 + (sg > 0 ? 0.004 : 0.003), T + G]], a0 + 0.004, a1 - 0.004, segs, false);      // facing up
        sweep(glass, sg > 0 ? [[edge - 0.003, T + 0.0002], [edge - 0.003, T + G]] : [[edge + 0.003, T + G], [edge + 0.003, T + 0.0002]], a0 + 0.004, a1 - 0.004, segs, false);
        sweep(wood, rect(edge - (sg > 0 ? 0.045 : -0.025), edge - (sg > 0 ? 0.025 : -0.045), 0.6, T - 0.04), a0, a1, segs, true, true);             // the apron
      }
      /* the end panels at the aisles and standards between the readers */
      for (const a of [a0, a1]) sweep(wood, [[rin, 0], [ro, 0], [ro, T - 0.04], [rc + hw, T - 0.04], [rc + hw, SP], [rc - hw, SP], [rc - hw, T - 0.04], [rin, T - 0.04]],
        a - (a === a0 ? 0 : 0.045 / rc), a + (a === a0 ? 0.045 / rc : 0), 1, true, true);
      for (let j = -n; j < n; j++) if ((j + n) % 2 === 1) { const a = sc + (j + 0.5) * step;
        sweep(wood, [[rin + 0.12, 0.08], [ro - 0.12, 0.08], [ro - 0.12, T - 0.04], [rin + 0.12, T - 0.04]], a - 0.015 / rc, a + 0.015 / rc, 1, true, true); }
    }
  }
  return {wood: wood.geometry(), tops: tops.geometry(), glass: glass.geometry(), books: books.geometry(), lamps};
}
/* the central desk: its round counter (open to the west), the shelved second tier with its brass rail, and the high desk
   at the top */
function centralDesk(){
  const W = new Mesher(), B = new Mesher(), dark = new Mesher(), top = new Mesher(), r0 = 3.72, r1 = 4.42, gate = 7.5 * D2R;
  const a0 = Math.PI + gate, a1 = 3 * Math.PI - gate;
  sweep(W, [[r0 + 0.04, 0], [r1 - 0.02, 0], [r1 - 0.02, 0.1], [r0 + 0.04, 0.1]], a0, a1, 96, true, true);
  sweep(W, [[r0 + 0.08, 0.1], [r1 - 0.06, 0.1], [r1 - 0.06, 0.995], [r0 + 0.08, 0.995]], a0, a1, 96, true, true);
  sweep(W, [[r0, 0.995], [r1 + 0.03, 0.995], [r1 + 0.03, 1.02], [r0, 1.02]], a0, a1, 96, true, true);
  sweep(top, [[r0, 1.02], [r1 + 0.035, 1.02], [r1 + 0.035, 1.048], [r0, 1.048]], a0, a1, 96, true, true);      // its polished top
  for (let i = 0; i <= 44; i++) {      // the counter's panels: stiles proud of its face
    const a = mix(a0, a1, i / 44);
    sweep(W, rect(r1 - 0.06, r1 - 0.035, 0.12, 0.97), a - 0.03 / r1, a + 0.03 / r1, 1, true, true);
  }
  sweep(W, rect(r1 - 0.06, r1 - 0.035, 0.52, 0.56), a0, a1, 96, true, false);
  for (const a of [a0, a1]) {      // the two posts of the gate
    const c = V3(Math.cos(a) * (r0 + r1) / 2, 0.68, Math.sin(a) * (r0 + r1) / 2), t = V3(-Math.sin(a), 0, Math.cos(a)), rr = V3(Math.cos(a), 0, Math.sin(a));
    W.box(c, [0.5, 1.36, 0.42], [t, V3(0, 1, 0), rr]); W.box(c.clone().setY(1.39), [0.56, 0.06, 0.48], [t, V3(0, 1, 0), rr]);
  }
  sweep(W, [[1.75, 0], [2.95, 0], [2.95, 1.05], [1.75, 1.05]], 0, 2 * Math.PI, 72, true, false);
  sweep(dark, [[1.85, 1.05], [2.86, 1.05], [2.86, 1.6], [1.85, 1.6]], 0, 2 * Math.PI, 72, true, false);
  sweep(W, [[2.55, 1.315], [2.9, 1.315], [2.9, 1.335], [2.55, 1.335]], 0, 2 * Math.PI, 72, true, false);      // the pigeonholes' shelf
  for (let i = 0; i < 36; i++) { const a = 2 * Math.PI * i / 36; sweep(W, rect(2.6, 2.9, 1.05, 1.6), a - 0.012, a + 0.012, 1, true, true); }
  sweep(W, [[1.8, 1.6], [3.0, 1.6], [3.0, 1.66], [1.8, 1.66]], 0, 2 * Math.PI, 72, true, false);
  sweep(top, [[1.8, 1.66], [3.03, 1.66], [3.03, 1.69], [1.8, 1.69]], 0, 2 * Math.PI, 72, true, false);
  sweep(W, [[2.95, 0.98], [3.0, 0.98], [3.0, 1.05], [2.95, 1.05]], 0, 2 * Math.PI, 72, true, false);
  for (let i = 0; i < 40; i++) { const a = 2 * Math.PI * (i + 0.5) / 40; sweep(W, rect(2.95, 2.975, 0.1, 0.95), a - 0.015, a + 0.015, 1, true, true); }
  sweep(B, [[2.93, 1.9], [2.95, 1.9], [2.95, 1.92], [2.93, 1.92]], 0, 2 * Math.PI, 96, true, false);
  for (let i = 0; i < 24; i++) { const a = 2 * Math.PI * i / 24; B.cyl(V3(Math.cos(a) * 2.94, 1.68, Math.sin(a) * 2.94), 0.008, 0.23, 6); }
  const bx = 0.15, bw = 1.3, bd = 2.1, bh = 2.45;
  W.box(V3(bx, bh / 2, 0), [bw, bh, bd]);
  top.box(V3(bx, bh + 0.03, 0), [bw + 0.12, 0.06, bd + 0.12]);
  W.box(V3(bx + 0.1, bh + 0.34, 0), [0.9, 0.56, 1.5]);
  top.box(V3(bx + 0.1, bh + 0.64, 0), [0.98, 0.05, 1.58]);
  /* panels on the high desk's sides: stiles and rails standing proud */
  for (const [cx, cz, nx, nz, len] of [[bx - bw / 2, 0, -1, 0, bd], [bx + bw / 2, 0, 1, 0, bd], [bx, bd / 2, 0, 1, bw], [bx, -bd / 2, 0, -1, bw]]) {
    const along = nx !== 0 ? V3(0, 0, 1) : V3(1, 0, 0), n = V3(nx, 0, nz), c = V3(cx, 0, cz).addScaledVector(n, 0.012);
    for (let i = 0; i <= 4; i++) W.box(c.clone().addScaledVector(along, -len / 2 + 0.04 + i * (len - 0.08) / 4).setY(1.95), [0.06, 1.0, 0.024], [along, V3(0, 1, 0), n]);
    for (const y of [1.46, 1.95, 2.42]) W.box(c.clone().setY(y), [len - 0.04, 0.05, 0.024], [along, V3(0, 1, 0), n]);
  }
  /* the louvred panels on its west face */
  for (const s of [-1, 1]) { W.box(V3(bx + 0.1 - 0.452, bh + 0.34, s * 0.38), [0.02, 0.4, 0.6]); for (let i = 0; i < 9; i++) dark.box(V3(bx + 0.1 - 0.465, bh + 0.2 + i * 0.034, s * 0.38), [0.012, 0.012, 0.54]); }
  return {wood: W.geometry(), brass: B.geometry(), dark: dark.geometry(), top: top.geometry()};
}
/* a reading chair, as one geometry: the sitter faces -z */
function chairGeometry(){
  const M = new Mesher(), sx = 0.215, sz = 0.2, Y = V3(0, 1, 0);
  M.box(V3(0, 0.455, 0), [0.46, 0.045, 0.44]);
  for (const [x, z] of [[-sx, -sz], [sx, -sz]]) M.box(V3(x, 0.217, z), [0.038, 0.434, 0.038]);
  for (const x of [-sx, sx]) M.box(V3(x, 0.47, sz + 0.01), [0.04, 0.94, 0.04], [V3(1, 0, 0), V3(0, 0.993, 0.12).normalize(), V3(0, -0.12, 0.993).normalize()]);
  M.box(V3(0, 0.88, sz + 0.06), [0.47, 0.085, 0.035], [V3(1, 0, 0), V3(0, 0.993, 0.12).normalize(), V3(0, -0.12, 0.993).normalize()]);
  M.box(V3(0, 0.66, sz + 0.035), [0.13, 0.34, 0.022], [V3(1, 0, 0), V3(0, 0.993, 0.12).normalize(), V3(0, -0.12, 0.993).normalize()]);
  for (const z of [-sz, sz]) M.box(V3(0, 0.16, z), [0.43, 0.025, 0.022]);
  for (const x of [-sx, sx]) M.box(V3(x, 0.13, 0), [0.022, 0.025, 0.4]);
  return M.geometry();
}
/* a desk lamp: a brass hood on two posts (its length along the ring), and the glowing underside */
function lampGeometry(){
  const M = new Mesher(), [L, H, D] = LAY.hood, y0 = LAY.hoodY - LAY.spine;
  /* the hood's section, extruded along its length: straight sides, a rounded shoulder, a flat crown */
  const sec = [[D / 2 + 0.006, 0], [D / 2, H * 0.12]];
  for (let i = 0; i <= 10; i++) { const a = Math.PI * i / 10; sec.push([D / 2 * Math.cos(a), H * 0.12 + H * 0.88 * Math.sin(a)]); }
  sec.push([-D / 2, H * 0.12], [-D / 2 - 0.006, 0]);
  const edgeN = i => { const [z0, h0] = sec[i], [z1, h1] = sec[i + 1], n = V3(0, -(z1 - z0), h1 - h0).normalize();
    return (n.y * (h0 + h1 - 2 * H * 0.12) + n.z * (z0 + z1) < 0) ? n.negate() : n; };      // outward, away from the section's middle
  const vN = sec.map((_, i) => (i === 0 ? edgeN(0) : i === sec.length - 1 ? edgeN(sec.length - 2) : edgeN(i - 1).add(edgeN(i)).normalize()));
  for (let i = 0; i < sec.length - 1; i++) {
    const [z0, h0] = sec[i], [z1, h1] = sec[i + 1], a = V3(-L / 2, y0 + h0, z0), b = V3(L / 2, y0 + h0, z0), c = V3(L / 2, y0 + h1, z1), d = V3(-L / 2, y0 + h1, z1);
    const n0 = vN[i], n1 = vN[i + 1], m0 = n0.clone().negate(), m1 = n1.clone().negate();
    M.tri(a, b, c, n0, n0, n1, [0, 0], [L, 0], [L, 0.1]); M.tri(a, c, d, n0, n1, n1, [0, 0], [L, 0.1], [0, 0.1]);
    M.tri(a, b, c, m0, m0, m1, [0, 0], [L, 0], [L, 0.1]); M.tri(a, c, d, m0, m1, m1, [0, 0], [L, 0.1], [0, 0.1]);      // its inside
  }
  for (const sx of [-1, 1]) {      // its two ends
    const pts = sec.map(([z, h]) => V3(sx * L / 2, y0 + h, z));
    for (let i = 1; i < pts.length - 1; i++) { M.tri(pts[0], pts[i], pts[i + 1], V3(sx, 0, 0), V3(sx, 0, 0), V3(sx, 0, 0), [0, 0], [0, 0], [0, 0]); M.tri(pts[0], pts[i], pts[i + 1], V3(-sx, 0, 0), V3(-sx, 0, 0), V3(-sx, 0, 0), [0, 0], [0, 0], [0, 0]); }
  }
  for (const x of [-L * 0.33, L * 0.33]) { M.cyl(V3(x, 0, 0), 0.007, y0, 8); M.box(V3(x, 0.006, 0), [0.05, 0.012, 0.05]); }
  /* the lit inside of the hood, up inside it so the hood's own sides hide it from a low side view, and the tube itself */
  const glow = new Mesher(), gy = y0 + H * 0.34, gd = D / 2 - 0.018;
  glow.quad(V3(-L / 2 + 0.014, gy, -gd), V3(L / 2 - 0.014, gy, -gd), V3(L / 2 - 0.014, gy, gd), V3(-L / 2 + 0.014, gy, gd), V3(0, -1, 0));
  glow.cyl(V3(-L * 0.4, gy + 0.008, 0), 0.011, L * 0.8, 8, [V3(0, 0, 1), V3(1, 0, 0), V3(0, 1, 0)]);
  return {hood: M.geometry(), glow: glow.geometry()};
}

/* ================================ the volume ================================ */
const BK = {W: 0.215, H: 0.29, T: 0.05, b: 0.0035, s: 0.004};
function bookBuild(A, lean, scene){
  const {W, H, T, b, s} = BK, grp = new THREE.Group(); scene.add(grp);
  const cov = {map: ctex(A.pics.cover.map), orm: ctex(A.pics.cover.orm, false)};
  const leather = new THREE.MeshStandardMaterial({map: cov.map, roughnessMap: cov.orm, metalnessMap: cov.orm, roughness: 1, metalness: 1, envMapIntensity: 1.1});
  const leatherPlain = new THREE.MeshStandardMaterial({color: "#5d2a20", roughness: 0.62, envMapIntensity: 1.0});
  if (A.leather[0]) { leatherPlain.map = texOf(A.leather[0], true, true); leatherPlain.map.repeat.set(3, 3); leatherPlain.color.set("#8c4636"); }
  if (A.leather[1]) { const nt = texOf(A.leather[1], false, true); leather.normalMap = nt; leatherPlain.normalMap = nt.clone(); leatherPlain.normalMap.repeat.set(3, 3); }
  const paperEdge = new THREE.MeshStandardMaterial({map: ctex(A.pics.edges), roughness: 0.9});
  const endpaper = new THREE.MeshStandardMaterial({color: "#e9e0cc", roughness: 0.92});
  const pageMat = tex => new THREE.MeshStandardMaterial({map: tex, roughness: 0.88, side: THREE.FrontSide});
  const tex = {};
  for (const k of Object.keys(PAGES)) { tex[k] = ctex(A.pics.pages[k]); tex[k].anisotropy = 16; }
  /* the closed volume, and the half that falls open: each half is a page block with its board under it. The left half
     turns about the spine; when it lies open, each block's top curves down into the gutter */
  const half = (top, side, sx) => {
    const g = new THREE.Group();
    const geo = new THREE.BoxGeometry(W, T / 2, H, 48, 1, 1); geo.translate(sx * W / 2, b + T / 4, 0);
    const blk = new THREE.Mesh(geo, [paperEdge, paperEdge, pageMat(top), paperEdge, paperEdge, paperEdge]);
    const board = new THREE.Mesh(new THREE.BoxGeometry(W + s, b, H + 2 * s).translate(sx * (W + s) / 2, b / 2, 0), side === "front" ? [leatherPlain, leatherPlain, endpaper, leather, leatherPlain, leatherPlain] : leatherPlain);
    blk.castShadow = blk.receiveShadow = board.castShadow = board.receiveShadow = true;
    g.add(blk, board);
    return {g, blk, geo, flat: Float32Array.from(geo.attributes.position.array)};
  };
  /* the front board sits at the bottom of the left half: turned over, it is the cover on top of the closed book */
  const right = half(tex.R3, "back", 1), left = half(tex.L0, "front", -1);
  /* closed, the cover lies on top turned end for end, so its title is drawn turned half round */
  for (const t of [cov.map, cov.orm]) { t.repeat.set(-1, -1); t.offset.set(1, 1); }
  grp.add(right.g, left.g);
  const spine = new THREE.Mesh(new THREE.CylinderGeometry(T / 2 + b, T / 2 + b, H + 2 * s, 20, 1, true, Math.PI, Math.PI).rotateX(Math.PI / 2).scale(0.42, 1, 1).translate(0, b + T / 2, 0), leatherPlain);
  spine.castShadow = true; grp.add(spine);
  /* the leaves that turn, each a strip bent along its width */
  const leaves = [];
  for (const [f, k] of [[tex.R0, tex.L1], [tex.R1, tex.L2], [tex.R2, tex.L3]]) {
    const geo = new THREE.PlaneGeometry(W, H, 28, 1);
    const front = new THREE.Mesh(geo, new THREE.MeshStandardMaterial({map: f, roughness: 0.88, side: THREE.FrontSide}));
    const back = new THREE.Mesh(geo, new THREE.MeshStandardMaterial({map: k, roughness: 0.88, side: THREE.BackSide}));
    k.wrapS = THREE.RepeatWrapping; k.repeat.x = -1; k.offset.x = 1;      // seen from behind, the back's text reads the right way
    front.castShadow = back.castShadow = true; front.receiveShadow = back.receiveShadow = true;
    const g = new THREE.Group(); g.add(front, back); grp.add(g);
    leaves.push({g, geo, n: geo.attributes.position.count});
  }
  /* where the blocks' tops curve into the gutter when open (y above the board, by x from the spine) */
  const curve = (x, open) => {
    const u = clamp(x / W), dip = open * (1 - Math.pow(u, 0.35)) * 0.011, rise = open * Math.sin(Math.PI * Math.pow(u, 0.7)) * 0.003;
    return b + T / 2 - dip + rise;
  };
  const shapeBlock = (h, open) => {      // lower the top of a half's block near the spine as the book opens
    const p = h.geo.attributes.position;
    for (let i = 0; i < p.count; i++) { const x = h.flat[i * 3], y = h.flat[i * 3 + 1];
      if (y > b + T / 4) p.setY(i, curve(Math.abs(x), open)); }
    p.needsUpdate = true; h.geo.computeVertexNormals();
  };
  /* a leaf lying on the right block, turning (u from 0 to 1) over to the left one: the part near the spine leads and the
     free edge trails, as paper does. Its shape is the block's curved top (the gutter's dip, the page's gentle rise),
     turned through the angle of the turn at each point along it, so at rest on either side it lies on its block exactly;
     the leaves stack, the first to turn on top on the right and lowest on the left */
  const LAYER = 0.0009, n = 28;
  const slope = (x, open) => { const e = 0.0015, a = Math.max(0, x - e), c = Math.min(W, x + e); return Math.atan2(curve(c, open) - curve(a, open), c - a); };
  const shapeLeaf = (L, u, k, open) => {
    const p = L.geo.attributes.position, lift = mix(LAYER * (3 - k) + 0.0006, LAYER * (k + 1) + 0.0006, smooth(u));
    let x = 0, y = curve(0, open) + lift, prevA = null;
    for (let i = 0; i <= n; i++) {
      if (i > 0) {
        const sN = (i - 0.5) / n, lag = clamp((u - 0.32 * sN) / (1 - 0.32 * sN * 0.999)), th = Math.PI * smooth(lag);
        const phi = slope(sN * W, open), a = th + phi * Math.cos(th);      // the page's own curve, mirrored as it goes over
        x += Math.cos(a) * W / n; y += Math.sin(a) * W / n;
      }
      p.setX(i, x); p.setY(i, y); p.setZ(i, -H / 2); p.setX(i + n + 1, x); p.setY(i + n + 1, y); p.setZ(i + n + 1, H / 2);
    }
    p.needsUpdate = true; L.geo.computeVertexNormals();
  };
  for (const L of leaves) L.geo.attributes.position.setUsage(THREE.DynamicDrawUsage);
  return {grp, left, right, spine, leaves, shapeBlock, shapeLeaf, mats: [leather, leatherPlain, paperEdge, endpaper]};
}

/* ================================ the lens: how the picture reaches the screen ================================ */
/* Everything is drawn first into a high-range picture with its depth, and the screen gets it through a lens (John,
   2026-10-11: "real lens behaviour"): a soft bloom off the windows, the lamps and the lantern; depth of field, the focus
   racking as the eye moves between the desk and the room; the shafts of sunlight, each an exact line integral of a soft
   cylinder of lit air along the eye's ray, cut off where the room's depth says the air ends; a filmic tone curve; a quiet
   grade (blacks lifted a touch, the midtones warm); the lens's own fall-off toward the edges and the colours focusing a
   hair apart there; and a very fine grain that changes every frame. The veil the crossing comes out of and goes into is
   laid on last. A lean device skips the depth of field, the multisampling and half the taps. */
const FS_VERT = "varying vec2 vUv; void main(){ vUv = uv; gl_Position = vec4(position.xy, 0.0, 1.0); }";
const NOISE_GLSL = `
  float hash12(vec2 p){ vec3 p3 = fract(vec3(p.xyx) * 0.1031); p3 += dot(p3, p3.yzx + 33.33); return fract((p3.x + p3.y) * p3.z); }
  float vnoise(vec2 p){ vec2 i = floor(p), f = fract(p); f = f * f * (3.0 - 2.0 * f);
    return mix(mix(hash12(i), hash12(i + vec2(1.0, 0.0)), f.x), mix(hash12(i + vec2(0.0, 1.0)), hash12(i + vec2(1.0, 1.0)), f.x), f.y); }`;
/* the cross-section of a shaft: a flat-topped beam with a soft edge (the lunette's own edge), crossed by the window's
   bars (a mullion every 1.25 m and a transom), the stained glass letting more through in some panes than others. dm: the
   distance from the beam's axis as a share of its radius; cx, cy: across the beam, metres (cx along the floor); ph: a phase
   of this beam's own */
const BEAM_PROF_GLSL = `
  float bhash(vec2 p){ vec3 p3 = fract(vec3(p.xyx) * 0.1031); p3 += dot(p3, p3.yzx + 33.33); return fract((p3.x + p3.y) * p3.z); }
  float beamProf(float dm, float cx, float cy, float ph){
    float edge = smoothstep(1.0, 0.86, dm);
    float mx = abs(fract(cx / 1.25 + 0.5) - 0.5) * 1.25;
    float bar = 1.0 - 0.82 * (1.0 - smoothstep(0.035, 0.08, mx));
    bar *= 1.0 - 0.7 * (1.0 - smoothstep(0.03, 0.07, abs(cy - 0.3)));
    float pane = 0.5 + 0.5 * bhash(vec2(floor(cx / 1.25 + 0.5), floor(cy / 0.9) + ph));
    return edge * bar * pane;
  }
  void beamAxes(vec3 u, out vec3 tb, out vec3 bb){ tb = normalize(vec3(-u.z, 0.0, u.x)); bb = cross(u, tb); }`;
const BEAM_GLSL = `
  uniform vec3 uBeamA[4], uBeamD[4]; uniform vec4 uBeamP[4]; uniform int uNBeam; uniform float uTime;
  ${BEAM_PROF_GLSL}
  /* the lit air of one shaft along the ray o + t d, up to tMax: the chord through its cylinder (radius, length, strength, a
     phase for its own haze in uBeamP), sampled along its length so the beam's edge and the window's bars hold from any angle,
     fading from the window down */
  float beamI(int i, vec3 o, vec3 rd, float tMax){
    vec3 A = uBeamA[i], u = uBeamD[i]; float R = uBeamP[i].x, L = uBeamP[i].y;
    vec3 w = o - A, rdp = rd - dot(rd, u) * u, wp = w - dot(w, u) * u;
    float a = dot(rdp, rdp), b = 2.0 * dot(rdp, wp), c = dot(wp, wp) - R * R;
    float t0, t1;
    if (a < 1e-5) { if (c > 0.0) return 0.0; t0 = 0.0; t1 = tMax; }
    else { float disc = b * b - 4.0 * a * c; if (disc <= 0.0) return 0.0; float sq = sqrt(disc); t0 = (-b - sq) / (2.0 * a); t1 = (-b + sq) / (2.0 * a); }
    float su = dot(rd, u), s0 = dot(w, u);
    if (abs(su) > 1e-5) { float ta = -s0 / su, tb = (L - s0) / su; t0 = max(t0, min(ta, tb)); t1 = min(t1, max(ta, tb)); }
    else if (s0 < 0.0 || s0 > L) return 0.0;
    t0 = max(t0, 0.0); t1 = min(t1, tMax);
    if (t1 <= t0) return 0.0;
    vec3 tb, bb; beamAxes(u, tb, bb);
    const int N = 7; float dt = (t1 - t0) / float(N), acc = 0.0;
    for (int k = 0; k < N; k++) {
      float t = t0 + (float(k) + 0.5) * dt; vec3 p = o + t * rd - A; float s = dot(p, u); vec3 q = p - s * u;
      float dm = length(q) / R, cx = dot(q, tb), cy = dot(q, bb);
      float fade = exp(-s / L * 1.15) * smoothstep(0.0, 0.06 * L, s);
      float n = vnoise(vec2(s * 0.3 - uTime * 0.025, dm * 2.5 + uBeamP[i].w + uTime * 0.01));
      acc += beamProf(dm, cx, cy, uBeamP[i].w) * fade * mix(0.72, 1.0, n) * dt;
    }
    return acc / R * uBeamP[i].z;
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
    const mat = (frag, uniforms) => new THREE.ShaderMaterial({uniforms, vertexShader: FS_VERT, fragmentShader: frag, depthTest: false, depthWrite: false});
    const T = "uniform sampler2D tex; uniform vec2 texel; varying vec2 vUv;";
    this.mBright = mat(`${T} uniform float thr, knee;
      void main(){ vec3 c = 0.25 * (texture2D(tex, vUv + texel * vec2(-0.5, -0.5)).rgb + texture2D(tex, vUv + texel * vec2(0.5, -0.5)).rgb + texture2D(tex, vUv + texel * vec2(-0.5, 0.5)).rgb + texture2D(tex, vUv + texel * vec2(0.5, 0.5)).rgb);
        float l = dot(c, vec3(0.2126, 0.7152, 0.0722)); float s = clamp(l - thr + knee, 0.0, 2.0 * knee); s = s * s / (4.0 * knee + 1e-4);
        float w = max(l - thr, s) / max(l, 1e-4); gl_FragColor = vec4(c * w, 1.0); }`,
      {tex: {value: null}, texel: {value: new THREE.Vector2()}, thr: {value: 0.96}, knee: {value: 0.22}});
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
    this.mFinal = mat(`${T} uniform sampler2D bloom, depth; uniform float expo, bloomK, grain, vig, ca, veilA, lift, warm, sat, frame, near, far, uSun;
      uniform vec3 veil, camPos; uniform mat4 invProj, camWorld;
      ${NOISE_GLSL}${BEAM_GLSL}
      vec3 aces(vec3 x){ return clamp((x * (2.51 * x + 0.03)) / (x * (2.43 * x + 0.59) + 0.14), 0.0, 1.0); }
      void main(){
        vec2 q = vUv - 0.5; float r2 = dot(q, q); vec2 off = q * ca * (0.4 + r2);
        vec3 col = vec3(texture2D(tex, vUv + off).r, texture2D(tex, vUv).g, texture2D(tex, vUv - off).b);
        if (uNBeam > 0) {
          float d = texture2D(depth, vUv).x;
          vec4 v = invProj * vec4(vUv * 2.0 - 1.0, d * 2.0 - 1.0, 1.0); v /= v.w; vec3 P = (camWorld * v).xyz;
          vec3 ray = P - camPos; float tS = length(ray); vec3 rd = ray / max(tS, 1e-4);
          float lit = 0.0; for (int i = 0; i < 4; i++) { if (i >= uNBeam) break; lit += beamI(i, camPos, rd, tS); }
          col += vec3(1.0, 0.9, 0.74) * lit * uSun;
        }
        col += texture2D(bloom, vUv).rgb * bloomK;
        col *= expo;
        col = aces(col);
        float l = dot(col, vec3(0.2126, 0.7152, 0.0722));
        col = mix(vec3(l), col, sat);
        col *= mix(vec3(1.0), vec3(1.035, 1.0, 0.955), warm * (1.0 - abs(l - 0.5) * 1.4));
        col = col * (1.0 - lift) + lift * vec3(0.98, 0.96, 1.0);
        col *= 1.0 - vig * smoothstep(0.12, 0.95, r2 * 2.0);
        float gn = hash12(floor(gl_FragCoord.xy / 1.5) + vec2(frame * 7.13, frame * 3.71)) - 0.5;
        col += gn * grain * (1.0 - 0.75 * l);
        col = mix(col, veil, veilA);
        gl_FragColor = vec4(col, 1.0);
        #include <colorspace_fragment>
      }`,
      {tex: {value: null}, texel: {value: new THREE.Vector2()}, bloom: {value: null}, depth: {value: null}, expo: {value: 1.0}, bloomK: {value: 0.26}, grain: {value: 0.028}, vig: {value: 0.3}, ca: {value: 0.0025},
       veilA: {value: 0}, veil: {value: new THREE.Color(0, 0, 0)}, uSun: {value: 1}, lift: {value: 0.018}, warm: {value: 0.5}, sat: {value: 1.04}, frame: {value: 0}, near: {value: 0.03}, far: {value: 200},
       camPos: {value: V3()}, invProj: {value: new THREE.Matrix4()}, camWorld: {value: new THREE.Matrix4()},
       uBeamA: {value: [V3(), V3(), V3(), V3()]}, uBeamD: {value: [V3(), V3(), V3(), V3()]}, uBeamP: {value: [new THREE.Vector4(), new THREE.Vector4(), new THREE.Vector4(), new THREE.Vector4()]}, uNBeam: {value: 0}, uTime: {value: 0}});
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
  /* draw: scene and camera into the lens, then to the canvas. P: {focus, aper, veil, veilA, expo, time, beams} */
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
    f.grain.value = this.lean ? 0.018 : 0.022; f.uSun.value = P.sun ?? 1;
    if (P.beams) { f.uNBeam.value = P.beams.n; for (let i = 0; i < 4; i++) { f.uBeamA.value[i].copy(P.beams.A[i]); f.uBeamD.value[i].copy(P.beams.D[i]); f.uBeamP.value[i].copy(P.beams.P[i]); } } else f.uNBeam.value = 0;
    this.pass(this.mFinal, src, null);
  }
  dispose(){ if (this.rts) for (const k in this.rts) this.rts[k].dispose(); for (const m of [this.mBright, this.mDown, this.mUp, this.mDof, this.mFinal]) m.dispose(); this.quad.geometry.dispose(); }
}

/* ================================ the shafts of sun, and the dust in them ================================ */
/* Where the sun comes in: a shaft from each lit window (the window's middle, at the back of its alcove), down across the
   room along the sun's own direction until it meets the floor. Set once into the uniforms the lens, the carpet and the
   desks share. */
function sunBeams(){
  const beams = {n: 0, A: [V3(), V3(), V3(), V3()], D: [V3(), V3(), V3(), V3()], P: [new THREE.Vector4(), new THREE.Vector4(), new THREE.Vector4(), new THREE.Vector4()]};
  const dir = SUN.clone().negate(), yWin = (ROOM.Win[1] + ROOM.Win[0] * 0.5) * FT, rWin = (ROOM.Rs + ROOM.Wa - 0.3) * FT;
  for (const [b, k] of SUN_BAYS) {
    const az = b * 45 * D2R, n = V3(Math.cos(az), 0, Math.sin(az));
    if (n.dot(SUN) < 0.15) continue;
    const A = n.clone().multiplyScalar(rWin).setY(yWin), L = (yWin - 0.05) / -dir.y;
    const i = beams.n++;
    beams.A[i].copy(A); beams.D[i].copy(dir); beams.P[i].set(2.55, L, 0.36 * k * n.dot(SUN), i * 7.3);
  }
  return beams;
}
/* The dust: motes drifting in the air, brightest where a shaft crosses them, faint elsewhere. Most are seeded inside the
   shafts; each drifts on its own slow path. Drawn as soft points, added to the light, never over anything nearer. */
function dustPoints(beams, lean, U){
  const N = lean ? 420 : 1500, pos = new Float32Array(N * 3), rnd = new Float32Array(N * 3), R = rng(31);
  for (let i = 0; i < N; i++) {
    let p;
    if (beams.n && R() < 0.8) {      // inside a shaft: along it, within its radius
      const bi = (R() * beams.n) | 0, A = beams.A[bi], D = beams.D[bi], Pb = beams.P[bi], s = R() * R() * Pb.y * 0.9, th = R() * 2 * Math.PI, rr = Math.sqrt(R()) * Pb.x * 0.95;
      const t = V3(-D.z, 0, D.x).normalize(), bn = D.clone().cross(t).normalize();
      p = A.clone().addScaledVector(D, s).addScaledVector(t, Math.cos(th) * rr).addScaledVector(bn, Math.sin(th) * rr);
      if (p.y < 0.2) p.y = 0.2 + R() * 2;
    } else {
      const rr = Math.sqrt(R()) * ROOM.Rs * FT * 0.95, th = R() * 2 * Math.PI;
      p = V3(Math.cos(th) * rr, 0.3 + Math.pow(R(), 1.5) * 20, Math.sin(th) * rr);
    }
    pos.set([p.x, p.y, p.z], i * 3); rnd.set([R(), R(), R()], i * 3);
  }
  const g = new THREE.BufferGeometry();
  g.setAttribute("position", new THREE.Float32BufferAttribute(pos, 3)); g.setAttribute("aRnd", new THREE.Float32BufferAttribute(rnd, 3));
  const m = new THREE.ShaderMaterial({
    uniforms: {uTime: U.uTime, uSize: {value: lean ? 70 : 104}, uSunI: U.uSunI, uBeamA: U.uBeamA, uBeamD: U.uBeamD, uBeamP: U.uBeamP, uNBeam: U.uNBeam, uDpr: {value: 1}},
    vertexShader: `attribute vec3 aRnd; uniform float uTime, uSize, uSunI, uDpr; uniform vec3 uBeamA[4], uBeamD[4]; uniform vec4 uBeamP[4]; uniform int uNBeam; varying float vI;
      ${BEAM_PROF_GLSL}
      void main(){
        float t = uTime * (0.6 + aRnd.z);
        vec3 p = position + vec3(sin(t * 0.21 + aRnd.x * 6.283) * 0.35, sin(t * 0.17 + aRnd.y * 6.283) * 0.2 - mod(uTime * 0.012 * (0.5 + aRnd.x), 1.6), cos(t * 0.19 + aRnd.z * 6.283) * 0.35);
        float lit = 0.36;
        for (int i = 0; i < 4; i++) { if (i >= uNBeam) break; vec3 w = p - uBeamA[i]; float s = dot(w, uBeamD[i]);
          if (s < 0.0 || s > uBeamP[i].y) continue; vec3 q = w - s * uBeamD[i]; float d = length(q) / uBeamP[i].x;
          vec3 tb, bb; beamAxes(uBeamD[i], tb, bb);
          lit += beamProf(d, dot(q, tb), dot(q, bb), uBeamP[i].w) * exp(-s / uBeamP[i].y * 1.4) * uBeamP[i].z * 22.0 * uSunI; }
        vec4 mv = modelViewMatrix * vec4(p, 1.0); float dist = max(0.3, -mv.z);
        gl_PointSize = clamp(uSize * uDpr / dist, 1.2 * uDpr, 7.0 * uDpr);
        vI = lit * (0.5 + 0.5 * sin(t * 1.3 + aRnd.y * 9.0)) * clamp(2.0 / dist, 0.15, 1.0);
        gl_Position = projectionMatrix * mv;
      }`,
    fragmentShader: `varying float vI; void main(){ vec2 q = gl_PointCoord - 0.5; float a = smoothstep(0.5, 0.1, length(q)); gl_FragColor = vec4(vec3(1.0, 0.94, 0.82) * vI * a, 1.0); }`,
    transparent: true, blending: THREE.AdditiveBlending, depthWrite: false, depthTest: true});
  const pts = new THREE.Points(g, m); pts.frustumCulled = false; pts.renderOrder = 5;
  return pts;
}

/* ================================ the sound of the room ================================ */
/* Off until the reader turns it on (John, 2026-10-11), and made here, on the device, with nothing fetched: the hush of a
   great stone room (filtered noise, very low, through a long reverberation made for the room's size), a footstep far off
   now and then with its echo, a page turned, a chair, the faint hum of the lamp at your own desk, and your own steps when
   you walk. Each sound is a few oscillators and a burst of noise shaped by envelopes. */
class RoomSound {
  constructor(){ this.ctx = null; this.on = false; this.timers = []; this.seat = "desk"; this.walking = false; this.near = 1; }
  start(){
    if (this.ctx) { if (this.ctx.state === "suspended") this.ctx.resume(); this.master.gain.setTargetAtTime(0.9, this.ctx.currentTime, 0.4); this.on = true; this.schedule(); return; }
    const AC = window.AudioContext || window.webkitAudioContext; if (!AC) return;
    const c = this.ctx = new AC(), t = c.currentTime;
    this.master = c.createGain(); this.master.gain.value = 0; this.master.connect(c.destination);
    this.master.gain.setTargetAtTime(0.9, t, 0.6);
    /* the room's reverberation: a long tail that darkens as it decays, made from noise */
    const conv = c.createConvolver(), sr = c.sampleRate, len = Math.floor(sr * 4.6), ir = c.createBuffer(2, len, sr);
    for (let ch = 0; ch < 2; ch++) { const d = ir.getChannelData(ch); let lp = 0; const R = rng(ch + 3);
      for (let i = 0; i < len; i++) { const x = i / sr, env = Math.exp(-x * 1.25) * (x < 0.012 ? x / 0.012 : 1), early = (i % Math.floor(sr * (0.043 + ch * 0.007)) < 60 && x < 0.35) ? 0.6 : 0;
        const n = (R() * 2 - 1); lp += (n - lp) * (0.35 - 0.3 * Math.min(1, x / 3)); d[i] = (lp * 1.6 + early * n) * env * 0.5; } }
    conv.buffer = ir; this.verb = c.createGain(); this.verb.gain.value = 0.55; conv.connect(this.verb); this.verb.connect(this.master); this.conv = conv;
    /* the hush: brown noise low-passed, and a breath of air higher up, through the room */
    const nb = c.createBuffer(1, sr * 4, sr), nd = nb.getChannelData(0); let b = 0; const R = rng(9);
    for (let i = 0; i < nd.length; i++) { const w = R() * 2 - 1; b = (b + 0.02 * w) / 1.02; nd[i] = b * 3.5; }
    const hush = c.createBufferSource(); hush.buffer = nb; hush.loop = true;
    const lpf = c.createBiquadFilter(); lpf.type = "lowpass"; lpf.frequency.value = 240; lpf.Q.value = 0.5;
    this.hushG = c.createGain(); this.hushG.gain.value = 0.11; hush.connect(lpf); lpf.connect(this.hushG); this.hushG.connect(this.master); this.hushG.connect(conv); hush.start();
    const air = c.createBufferSource(); air.buffer = nb; air.loop = true; air.playbackRate.value = 1.9;
    const bp = c.createBiquadFilter(); bp.type = "bandpass"; bp.frequency.value = 2600; bp.Q.value = 0.7;
    const airG = c.createGain(); airG.gain.value = 0.006; air.connect(bp); bp.connect(airG); airG.connect(this.master); air.start();
    /* the lamp at your desk: a faint hum, only when you sit at a desk */
    const hum = c.createOscillator(), hum2 = c.createOscillator(); hum.frequency.value = 120; hum2.frequency.value = 240;
    this.humG = c.createGain(); this.humG.gain.value = 0; hum.connect(this.humG); hum2.connect(this.humG); this.humG.connect(this.master); hum.start(); hum2.start();
    this.hum2G = c.createGain(); this.hum2G.gain.value = 0.3; hum2.disconnect(); hum2.connect(this.hum2G); this.hum2G.connect(this.humG);
    this.on = true; this.place(this.seat, this.walking);
    this.schedule();
  }
  stop(){ if (!this.ctx) return; this.on = false; this.master.gain.setTargetAtTime(0, this.ctx.currentTime, 0.25); for (const id of this.timers) clearTimeout(id); this.timers = [];
    setTimeout(() => { if (!this.on && this.ctx && this.ctx.state === "running") this.ctx.suspend(); }, 900); }
  close(){ for (const id of this.timers) clearTimeout(id); this.timers = []; if (this.ctx) { try { this.ctx.close(); } catch (e) {} this.ctx = null; } this.on = false; }
  /* where the listener is: the hum of the lamp near the desks, more echo and less hush from the gallery */
  place(seat, walking){
    this.seat = seat; this.walking = !!walking;
    if (!this.ctx) return;
    const t = this.ctx.currentTime;
    this.humG.gain.setTargetAtTime(seat === "desk" && !walking ? 0.0045 : 0, t, 0.5);
    this.verb.gain.setTargetAtTime(seat === "gallery" ? 0.7 : 0.55, t, 0.5);
    this.hushG.gain.setTargetAtTime(seat === "gallery" ? 0.08 : 0.11, t, 0.5);
  }
  noise(dur, color = 1){
    const c = this.ctx, n = Math.ceil(c.sampleRate * dur), buf = c.createBuffer(1, n, c.sampleRate), d = buf.getChannelData(0); let lp = 0;
    for (let i = 0; i < n; i++) { const w = Math.random() * 2 - 1; lp += (w - lp) * color; d[i] = lp; }
    const s = c.createBufferSource(); s.buffer = buf; return s;
  }
  out(node, pan, wet, dry){
    const c = this.ctx, p = c.createStereoPanner ? c.createStereoPanner() : null;
    const gd = c.createGain(), gw = c.createGain(); gd.gain.value = dry; gw.gain.value = wet;
    if (p) { p.pan.value = pan; node.connect(p); p.connect(gd); p.connect(gw); } else { node.connect(gd); node.connect(gw); }
    gd.connect(this.master); gw.connect(this.conv);
  }
  /* one footstep: a low thump and a heel's click; far (mostly echo) or your own (dry, under you) */
  step(when, far, pan){
    const c = this.ctx, g = c.createGain(), o = c.createOscillator(); o.type = "sine"; o.frequency.setValueAtTime(far ? 95 : 70, when); o.frequency.exponentialRampToValueAtTime(42, when + 0.09);
    g.gain.setValueAtTime(0, when); g.gain.linearRampToValueAtTime(far ? 0.05 : 0.12, when + 0.006); g.gain.exponentialRampToValueAtTime(0.001, when + 0.14);
    o.connect(g); this.out(g, pan, far ? 0.9 : 0.25, far ? 0.08 : 0.5); o.start(when); o.stop(when + 0.16);
    const n = this.noise(0.03, 0.9), f = c.createBiquadFilter(); f.type = "bandpass"; f.frequency.value = far ? 2200 : 1500; f.Q.value = 1.2;
    const ng = c.createGain(); ng.gain.setValueAtTime(0, when); ng.gain.linearRampToValueAtTime(far ? 0.05 : 0.09, when + 0.003); ng.gain.exponentialRampToValueAtTime(0.001, when + 0.03);
    n.connect(f); f.connect(ng); this.out(ng, pan, far ? 0.9 : 0.3, far ? 0.06 : 0.45); n.start(when); n.stop(when + 0.04);
  }
  farSteps(){
    const c = this.ctx, n = 4 + Math.floor(Math.random() * 6), pan = (Math.random() - 0.5) * 1.4, gap = 0.52 + Math.random() * 0.12;
    let t = c.currentTime + 0.1;
    for (let i = 0; i < n; i++) { this.step(t, true, pan * (1 - i / n * 0.3)); t += gap * (0.96 + Math.random() * 0.08); }
  }
  page(){
    const c = this.ctx, when = c.currentTime + 0.05, pan = (Math.random() - 0.5) * 1.2;
    for (const [dt, dur, f0, f1, g0] of [[0, 0.16, 900, 3800, 0.05], [0.19, 0.11, 2400, 1200, 0.035]]) {
      const n = this.noise(dur, 0.6), bp = c.createBiquadFilter(); bp.type = "bandpass"; bp.Q.value = 0.9;
      bp.frequency.setValueAtTime(f0, when + dt); bp.frequency.exponentialRampToValueAtTime(f1, when + dt + dur);
      const g = c.createGain(); g.gain.setValueAtTime(0, when + dt); g.gain.linearRampToValueAtTime(g0, when + dt + dur * 0.35); g.gain.linearRampToValueAtTime(0, when + dt + dur);
      n.connect(bp); bp.connect(g); this.out(g, pan, 0.5, 0.35); n.start(when + dt); n.stop(when + dt + dur + 0.01);
    }
  }
  chair(){
    const c = this.ctx, when = c.currentTime + 0.05, pan = (Math.random() - 0.5) * 1.4, creak = Math.random() < 0.5;
    if (creak) {
      const o = c.createOscillator(); o.type = "sawtooth"; o.frequency.setValueAtTime(70 + Math.random() * 40, when); o.frequency.linearRampToValueAtTime(95 + Math.random() * 40, when + 0.25);
      const f = c.createBiquadFilter(); f.type = "bandpass"; f.frequency.value = 900; f.Q.value = 6;
      const g = c.createGain(); g.gain.setValueAtTime(0, when); g.gain.linearRampToValueAtTime(0.03, when + 0.08); g.gain.linearRampToValueAtTime(0, when + 0.32);
      o.connect(f); f.connect(g); this.out(g, pan, 0.6, 0.3); o.start(when); o.stop(when + 0.35);
    } else {
      const n = this.noise(0.45, 0.08), g = c.createGain(); g.gain.setValueAtTime(0, when); g.gain.linearRampToValueAtTime(0.09, when + 0.12); g.gain.linearRampToValueAtTime(0, when + 0.45);
      n.connect(g); this.out(g, pan, 0.7, 0.25); n.start(when); n.stop(when + 0.5);
    }
  }
  door(){
    const c = this.ctx, when = c.currentTime + 0.05, o = c.createOscillator(); o.type = "sine"; o.frequency.setValueAtTime(60, when); o.frequency.exponentialRampToValueAtTime(30, when + 0.25);
    const g = c.createGain(); g.gain.setValueAtTime(0, when); g.gain.linearRampToValueAtTime(0.12, when + 0.01); g.gain.exponentialRampToValueAtTime(0.001, when + 0.4);
    o.connect(g); this.out(g, (Math.random() - 0.5) * 1.2, 1.0, 0.05); o.start(when); o.stop(when + 0.45);
  }
  schedule(){
    for (const id of this.timers) clearTimeout(id); this.timers = [];
    const later = (f, lo, hi) => { const go = () => { if (!this.on) return; try { f(); } catch (e) {} this.timers.push(setTimeout(go, (lo + Math.random() * (hi - lo)) * 1000)); };
      this.timers.push(setTimeout(go, (lo + Math.random() * (hi - lo)) * 1000)); };
    later(() => this.farSteps(), 9, 28); later(() => this.page(), 7, 24); later(() => this.chair(), 18, 50); later(() => this.door(), 70, 160);
  }
  /* your own footstep as you walk */
  ownStep(){ if (!this.on || !this.ctx) return; this.step(this.ctx.currentTime + 0.01, false, (Math.random() - 0.5) * 0.3); }
  pause(){ if (this.ctx && this.ctx.state === "running") this.ctx.suspend(); }
  resume(){ if (this.ctx && this.on && this.ctx.state === "suspended") this.ctx.resume(); }
}

/* ================================ where the floor is: the walker's rules ================================ */
/* Where a reader on foot may stand (nothing walks through a wall or a desk): the floor of the room inside the octagon,
   clear of the piers' bases, the three rings of desks (with their chairs) except through the aisles, and the central
   desk's counter except in through its gate and round the librarians' passage inside; or the floor of the visitors'
   gallery, the west alcove's upper room. A point is tried as a whole, then along each axis, so a reader slides along
   what they meet. */
const WALK = {
  octagon: (ROOM.Rs - 1.8) * FT, pierR: 2.7, pierAt: (ROOM.Rcc - 0.6) * FT,
  rings: LAY.rings.map((r, i) => ({rc: r.rc, half: i === 0 ? 0.31 + 0.36 : LAY.hw + LAY.depth + 0.41, ang: 22.5 * D2R - Math.atan(LAY.aisle / 2 / r.rc) + 0.012})),
  counterOut: 4.42 + 0.38, counterIn: 3.72 - 0.15, tierOut: 3.0 + 0.15, gate: 7.5 * D2R - 0.2 / 4.07
};
const wrapA = a => { a = (a + Math.PI) % (2 * Math.PI); if (a < 0) a += 2 * Math.PI; return a - Math.PI; };
function floorOK(x, z){
  const r = Math.hypot(x, z), az = Math.atan2(z, x);
  /* the octagon, as the distance to the nearest of its eight faces */
  const face = Math.round(az / (45 * D2R)) * 45 * D2R;
  if (r * Math.cos(az - face) > WALK.octagon) return false;
  const pa = Math.round((az - 22.5 * D2R) / (45 * D2R)) * 45 * D2R + 22.5 * D2R;      // the nearest pier
  if (Math.hypot(x - Math.cos(pa) * WALK.pierAt, z - Math.sin(pa) * WALK.pierAt) < WALK.pierR) return false;
  for (const ring of WALK.rings) {
    if (Math.abs(r - ring.rc) > ring.half) continue;
    const sc = Math.round((az - 22.5 * D2R) / (45 * D2R)) * 45 * D2R + 22.5 * D2R;
    if (Math.abs(wrapA(az - sc)) < ring.ang) return false;
  }
  if (r < WALK.counterOut) {      // the central desk: through the gate, and round the passage inside
    const inGate = Math.abs(wrapA(az - Math.PI)) < WALK.gate;
    if (r > WALK.counterIn) return inGate;
    return r > WALK.tierOut;
  }
  return true;
}
/* the gallery's floor: u along the screen, w back from it (metres), in the west bay's frame */
const GAL = {u: (ROOM.Ua - 1.2) * FT, w0: 0.75, w1: (ROOM.Wa - 1.0) * FT};
function galleryOK(x, z){ const w = -x - ROOM.Rs * FT, u = -z; return Math.abs(u) < GAL.u && w > GAL.w0 && w < GAL.w1; }

/* ================================ the scene ================================ */
function build(renderer, aspect, A, opts = {}){
  const marks = [["start", performance.now()]], mark = n => marks.push([n, performance.now()]);
  const lean = !!A.lean, STILL = !!opts.still, R = rng(opts.seed != null ? opts.seed : 11);
  const scene = new THREE.Scene(); scene.background = new THREE.Color("#0b0806");
  const cam = new THREE.PerspectiveCamera(55, aspect, 0.03, 200); scene.add(cam);
  const beams = sunBeams(), room = !!(A.room || opts.room);
  const U = {uExpo: {value: 1.0}, uLampI: {value: 0.48}, uHeroAz: {value: LAY.heroAz * D2R}, uSunI: {value: opts.sun != null ? opts.sun : 1.0}, uTime: {value: 0},
             uBeamA: {value: beams.A}, uBeamD: {value: beams.D}, uBeamP: {value: beams.P}, uNBeam: {value: beams.n}};
  const kw = A.kw || (lean ? 0.5 : 1), kd = A.kd || (lean ? 0.5 : 1);

  /* ---------- the room, from the photographs ---------- */
  const wallsTex = texOf(A.walls, true), domeTex = texOf(A.dome, true);
  for (const t of [wallsTex, domeTex]) { t.generateMipmaps = true; t.minFilter = THREE.LinearMipmapLinearFilter; t.anisotropy = renderer.capabilities.getMaxAnisotropy(); }
  const G = buildRoom();
  const pc = projectorCamera(PHOTO.walls, 1), dk = lean ? 0.25 : room ? 0.55 : 0.4;
  const rt = new THREE.WebGLRenderTarget(Math.round(PHOTO.walls.w * dk), Math.round(PHOTO.walls.h * dk), {minFilter: THREE.NearestFilter, magFilter: THREE.NearestFilter});
  const dmat = depthMaterial(); dmat.uniforms.uPos.value.set(...PHOTO.walls.pos); dmat.uniforms.uF.value.set(...PHOTO.walls.F);
  const wallsMat = wallsMaterial(wallsTex, rt.texture, kw, U), domeMat = domeMaterial(domeTex, kd, U);
  const walls = new THREE.Mesh(G.walls, wallsMat), dome = new THREE.Mesh(G.dome, domeMat);
  walls.frustumCulled = dome.frustumCulled = false;
  scene.add(walls, dome);
  { const ds = new THREE.Scene(); ds.add(new THREE.Mesh(G.walls, dmat), new THREE.Mesh(G.dome, dmat));
    renderer.setRenderTarget(rt); renderer.setClearColor(0xffffff, 1); renderer.clear(); renderer.render(ds, pc); renderer.setRenderTarget(null); renderer.setClearColor(0x000000, 1); }

  mark("room");
  /* ---------- the floor: the carpet, and the wreathed books in the aisles ---------- */
  const cTex = ctex(A.pics.carpet); cTex.wrapS = cTex.wrapT = THREE.RepeatWrapping;
  const floorGeo = new THREE.CircleGeometry(ROOM.Rs / Math.cos(22.5 * D2R) * FT, 8, 22.5 * D2R).rotateX(-Math.PI / 2);
  { const p = floorGeo.attributes.position, uv = floorGeo.attributes.uv; for (let i = 0; i < p.count; i++) uv.setXY(i, p.getX(i) / CARPET_TILE, p.getZ(i) / CARPET_TILE); }
  const carpet = new THREE.MeshStandardMaterial({map: cTex, color: "#e9e4dc", roughness: 0.97, envMapIntensity: 0.5});
  if (A.carpetN) { carpet.normalMap = texOf(A.carpetN, false, true); carpet.normalMap.repeat.set(CARPET_TILE / 0.5, CARPET_TILE / 0.5); carpet.normalScale.set(0.6, 0.6);
  }
  lampPools(carpet, U); underDesks(carpet);
  const floor = new THREE.Mesh(floorGeo, carpet); floor.receiveShadow = true; scene.add(floor);
  const medMat = new THREE.MeshStandardMaterial({map: ctex(A.pics.medallion), transparent: true, roughness: 0.97, depthWrite: false, polygonOffset: true, polygonOffsetFactor: -2, envMapIntensity: 0.55});
  const medGeo = new THREE.PlaneGeometry(1.45, 1.45).rotateX(-Math.PI / 2);
  for (let k = 0; k < 8; k++) for (const r of [24.3 * FT, 35.7 * FT]) {
    const m = new THREE.Mesh(medGeo, medMat), a = k * 45 * D2R; m.position.set(Math.cos(a) * r, 0.002, Math.sin(a) * r); m.rotation.y = -a - Math.PI / 2; m.renderOrder = 1; scene.add(m);
  }

  mark("carpet");
  /* ---------- the desks, the lamps, the chairs, the central desk ---------- */
  /* the mahogany: the photographed map is a very dark wood (its mean is near black in green and blue), so its colour is
     brought up in linear light to the polished red-brown the Library's own photographs show, the tops a little less (your
     lamp is on them already) */
  const mahog = wood(A, lean, {tint: new THREE.Color().setRGB(1.9, 2.3, 2.3, THREE.LinearSRGBColorSpace), rough: 0.42, coat: 0.4});
  mahog.clearcoatRoughness = 0.22;
  /* the plate glass on the desks: glossy, but its picture of the room (taken from where you stand) is kept soft, or the
     lantern's blue, mirrored at the foot of a downward look, lies on the mahogany as a purple stain; and your lamp's
     glint spreads as a lamp's does, not a point */
  const mahogTop = wood(A, lean, {tint: new THREE.Color().setRGB(1.35, 1.6, 1.6, THREE.LinearSRGBColorSpace), rough: 0.4, coat: 0.2, wear: A.pics.wear});
  mahogTop.clearcoatRoughness = 0.16;
  lampPools(mahog, U); lampPools(mahogTop, U); softGlint(mahogTop, 0.1);
  const D = deskRings();
  const desks = new THREE.Mesh(D.wood, mahog); desks.receiveShadow = true; scene.add(desks);
  const deskTops = new THREE.Mesh(D.tops, mahogTop); deskTops.receiveShadow = true; scene.add(deskTops);
  scene.add(new THREE.Mesh(D.glass, new THREE.MeshStandardMaterial({color: "#5f8f78", roughness: 0.15, envMapIntensity: 1.2})));
  const bookTex = ctex(A.pics.spines); bookTex.wrapS = THREE.RepeatWrapping; bookTex.repeat.set(1 / 1.2, 1 / 0.74); bookTex.offset.y = -0.12 / 0.74;
  const shelf = new THREE.Mesh(D.books, new THREE.MeshStandardMaterial({map: bookTex, roughness: 0.7, envMapIntensity: 0.6})); scene.add(shelf);
  /* polished, lacquered brass: the room and the dome catch on the hoods' shoulders */
  const brass = new THREE.MeshPhysicalMaterial({color: "#7a5b2a", metalness: 1, roughness: 0.25, clearcoat: 0.6, clearcoatRoughness: 0.1});
  const LG = lampGeometry(), nL = D.lamps.length;
  const hoods = new THREE.InstancedMesh(LG.hood, brass, nL), glows = new THREE.InstancedMesh(LG.glow, new THREE.MeshBasicMaterial({color: new THREE.Color(1.0, 0.86, 0.62).multiplyScalar(2.6), side: THREE.DoubleSide}), nL);
  const mtx = new THREE.Matrix4(), q = new THREE.Quaternion(), one = V3(1, 1, 1);
  D.lamps.forEach((L, i) => {
    const top = L.ri === 0 ? 1.1 : LAY.spine;
    q.setFromAxisAngle(V3(0, 1, 0), -L.a - Math.PI / 2);
    mtx.compose(V3(Math.cos(L.a) * L.rc, top, Math.sin(L.a) * L.rc), q, one); hoods.setMatrixAt(i, mtx); glows.setMatrixAt(i, mtx);
  });
  scene.add(hoods, glows);
  const chairs = [];
  for (const ri of [1, 2]) {
    const {rc} = LAY.rings[ri], ro = rc + LAY.hw + LAY.depth, rin = rc - LAY.hw - LAY.depth;
    for (const L of D.lamps) if (L.ri === ri) for (const sg of [1, -1]) {
      if (ri === LAY.heroRing && sg === 1 && Math.abs(L.a - LAY.heroAz * D2R) < 0.002) continue;      // you stand there
      if (R() < 0.12) continue;
      const out = 0.08 + R() * 0.16, r = sg > 0 ? ro + out : rin - out, a = L.a + (R() - 0.5) * 0.04 / rc;
      chairs.push({p: V3(Math.cos(a) * r, 0, Math.sin(a) * r), face: a + (sg > 0 ? Math.PI : 0), turn: (R() - 0.5) * 0.25});
    }
  }
  const chairMesh = new THREE.InstancedMesh(chairGeometry(), mahog, chairs.length);
  const blob = drawn(64, 64, (g, w) => { const r = g.createRadialGradient(w / 2, w / 2, 0, w / 2, w / 2, w / 2);
    r.addColorStop(0, "rgba(0,0,0,.5)"); r.addColorStop(0.55, "rgba(0,0,0,.28)"); r.addColorStop(1, "rgba(0,0,0,0)"); g.fillStyle = r; g.fillRect(0, 0, w, w); });
  const shadows = new THREE.InstancedMesh(new THREE.PlaneGeometry(0.72, 0.68).rotateX(-Math.PI / 2), new THREE.MeshBasicMaterial({map: ctex(blob, false), transparent: true,
    depthWrite: false, polygonOffset: true, polygonOffsetFactor: -3, toneMapped: false}), chairs.length);
  shadows.renderOrder = 2;
  chairs.forEach((c, i) => {
    /* the sitter faces -z: turn it to face the desk */
    const f = dirAz(c.face / D2R).negate(); q.setFromAxisAngle(V3(0, 1, 0), Math.atan2(f.x, f.z) + c.turn);
    mtx.compose(c.p, q, one); chairMesh.setMatrixAt(i, mtx);
    mtx.compose(c.p.clone().setY(0.003), q, one); shadows.setMatrixAt(i, mtx);
  });
  scene.add(chairMesh, shadows);
  const CD = centralDesk();
  scene.add(new THREE.Mesh(CD.wood, mahog), new THREE.Mesh(CD.brass, brass), new THREE.Mesh(CD.dark, new THREE.MeshStandardMaterial({color: "#26170f", roughness: 0.85})),
    new THREE.Mesh(CD.top, (() => { const m = new THREE.MeshPhysicalMaterial({color: "#3a2a20", roughness: 0.25, clearcoat: 1, clearcoatRoughness: 0.05, envMapIntensity: 1.1}); softGlint(m, 0.1); return m; })()));

  /* the dust in the air, and in the shafts of sun */
  const dust = dustPoints(beams, lean, U); scene.add(dust);

  mark("furniture");
  /* ---------- the room's light on all of it: the room itself, seen from where you stand ---------- */
  const heroDir = dirAz(LAY.heroAz), EYE = heroDir.clone().multiplyScalar(LAY.eyeR).setY(LAY.eyeY);
  const cubeRT = new THREE.WebGLCubeRenderTarget(lean ? 256 : 512, {type: THREE.HalfFloatType});
  const cubeCam = new THREE.CubeCamera(0.1, 120, cubeRT); cubeCam.position.copy(EYE).setY(1.3); scene.add(cubeCam);
  const pmrem = new THREE.PMREMGenerator(renderer), envRT = pmrem.fromCubemap(cubeRT.texture);      // dark for now: filled once the room can be drawn
  scene.environment = envRT.texture; scene.environmentIntensity = 1.2;
  /* the room's fill on the furniture: the desks and the central desk are polished mahogany under a bright dome and a
     hundred lamps, and in the Library's own photographs they read as light as the piers' bases, not as black shapes */
  scene.add(new THREE.HemisphereLight("#fff1dc", "#6a5444", 0.85));

  /* ---------- the seats, in the room (metres; yaw 0 east, + toward the south) ---------- */
  const baseYaw0 = Math.atan2(-heroDir.z, -heroDir.x) / D2R;
  const seats = {
    desk: {pos: heroDir.clone().multiplyScalar(LAY.eyeR + 0.08).setY(SEATS[0].eye), yaw: baseYaw0, pitch: -5, floor: 0, eye: SEATS[0].eye,
           up: heroDir.clone().multiplyScalar(LAY.eyeR + 0.42).setY(STAND_EYE)},
    gallery: {pos: V3(-(ROOM.Rs + 2.6) * FT, ROOM.Hg * FT + SEATS[1].eye, 0.0), yaw: 0, pitch: -11, floor: ROOM.Hg * FT, eye: SEATS[1].eye,
              up: V3(-(ROOM.Rs + 3.4) * FT, ROOM.Hg * FT + STAND_EYE, 0.0)},
    centre: {pos: V3(Math.cos(150 * D2R) * 3.36, SEATS[2].eye, Math.sin(150 * D2R) * 3.36), yaw: 180, pitch: -3, floor: 0, eye: SEATS[2].eye,
             up: V3(Math.cos(150 * D2R) * 3.36, STAND_EYE, Math.sin(150 * D2R) * 3.36)}
  };

  mark("environment");
  /* ---------- your lamp: a real light, with shadows, for the volume ---------- */
  const heroLampPos = heroDir.clone().multiplyScalar(LAY.rings[1].rc).setY(LAY.hoodY - 0.02);
  const LAMP = 1.1, lamp = new THREE.SpotLight("#ffd29c", LAMP, 3.2, 1.05, 0.75, 2);
  lamp.position.copy(heroLampPos);
  const toEye = heroDir.clone();      // the volume lies on your side of the lamp
  const bookAt = heroDir.clone().multiplyScalar(LAY.rings[1].rc + LAY.hw + LAY.depth - 0.33).setY(LAY.top + LAY.glass);
  lamp.target.position.copy(bookAt).addScaledVector(toEye, -0.05);
  lamp.castShadow = true; lamp.shadow.mapSize.setScalar(lean ? 512 : 1024); lamp.shadow.bias = -0.0004; lamp.shadow.normalBias = 0.01;
  lamp.shadow.camera.near = 0.05; lamp.shadow.camera.far = 3;
  scene.add(lamp, lamp.target);
  renderer.shadowMap.enabled = true; renderer.shadowMap.type = THREE.PCFSoftShadowMap;

  /* ---------- the volume ---------- */
  const BOOK = bookBuild(A, lean, scene);
  const F = heroDir.clone().negate(), Rv = V3(-F.z, 0, F.x);      // facing the centre, and your right
  const bookBasis = new THREE.Matrix4().makeBasis(Rv, V3(0, 1, 0), F.clone().negate());
  const qFlat = new THREE.Quaternion().setFromRotationMatrix(bookBasis);
  const spineAt = bookAt.clone().addScaledVector(Rv, -0.01);      // the open volume is centred on the spine
  /* where your hands hold it, before it is set down: low, close, its cover toward you */
  const handAt = EYE.clone().addScaledVector(F, 0.46).addScaledVector(Rv, -0.06).add(V3(0, -0.72, 0));
  const qHand = qFlat.clone().multiply(new THREE.Quaternion().setFromEuler(new THREE.Euler(0.95, 0, -0.08)));

  mark("volume");
  /* ---------- where you look, second by second ---------- */
  const pose = {pos: V3(), yaw: 0, pitch: 0, roll: 0, zoom: 1};
  const baseYaw = baseYaw0;      // toward the room's centre
  const lookAtBook = (() => { const d = bookAt.clone().addScaledVector(Rv, -0.02).sub(EYE.clone().addScaledVector(F, 0.24).add(V3(0, -0.12, 0)));
    return {yaw: Math.atan2(d.z, d.x) / D2R, pitch: Math.atan2(d.y, Math.hypot(d.x, d.z)) / D2R}; })();
  /* the still picture: a step back from your desk, the record open on it and the room beyond (the crossing ends here too) */
  const STILL_POS = EYE.clone().addScaledVector(heroDir, 0.42).add(V3(0, 0.06, 0));
  const STILL_LOOK = (() => { const d = bookAt.clone().sub(STILL_POS); return {yaw: Math.atan2(d.z, d.x) / D2R + 1, pitch: -17, zoom: 1.06}; })();
  /* the weight of a head (John, 2026-10-11: "weighted, eased camera moves"): the path is eased end to end, and on it rides
     the small unsteadiness of a person standing: a slow sway, the breath, and a tremor too fine to see but felt. k scales
     it down when the eye settles on the page */
  const hand = (t, k) => ({yaw: k * (0.22 * Math.sin(t * 0.53 + 1.3) + 0.09 * Math.sin(t * 1.71 + 0.2) + 0.03 * Math.sin(t * 4.3)),
                           pitch: k * (0.16 * Math.sin(t * 0.47) + 0.08 * Math.sin(t * 1.45 + 0.4) + 0.025 * Math.sin(t * 3.9 + 1)),
                           roll: k * (0.22 * Math.sin(t * 0.33 + 0.7) + 0.04 * Math.sin(t * 2.1))});
  const poseAt = (t) => {
    if (STILL) {
      pose.pos.copy(STILL_POS); pose.yaw = STILL_LOOK.yaw; pose.pitch = STILL_LOOK.pitch; pose.roll = 0; pose.zoom = STILL_LOOK.zoom;
      return pose;
    }
    const rise = sine(seg(t, 1.1, 4.15)), dwell = smooth(seg(t, 4.15, 4.85)), down = sine(seg(t, 4.75, 6.6)), back = sine(seg(t, 8.15, 9.8));
    /* up to the dome, but the frame's top edge goes hardly past straight up: what is above and behind you is what the
       photographs saw least of */
    const top = Math.min(72, 89 - vfov(cam.aspect) / 2) - 2.5;
    let pitch = mix(-0.5, 1.5, smooth(seg(t, 0, 1.1)));
    pitch = mix(pitch, top, rise); pitch += 2.5 * dwell;
    pitch = mix(pitch, lookAtBook.pitch + 4, down);
    pitch = mix(pitch, lookAtBook.pitch + 1, smooth(seg(t, 6.6, 8.15)));
    let yaw = baseYaw - 9 + 2.5 * smooth(seg(t, 0, 1.1)) + 9 * rise - 3 * dwell;
    yaw = mix(yaw, lookAtBook.yaw + 1.5, down);
    yaw = mix(yaw, lookAtBook.yaw + 0.5, smooth(seg(t, 6.6, 8.15)));
    const pos = EYE.clone();
    /* you step up to the desk and bend a little over it as you look down to it */
    pos.addScaledVector(F, 0.24 * sine(seg(t, 5.0, 6.9))).add(V3(0, -0.12 * sine(seg(t, 5.2, 7.0)), 0));
    /* breathing, a slight sway */
    pos.y += 0.006 * Math.sin(t * 1.5);
    pos.addScaledVector(Rv, 0.005 * Math.sin(t * 0.55));
    /* as the leaves turn you straighten up and step back, and the room stands around the record open on your desk: the
       view the still picture keeps */
    pos.lerp(STILL_POS, back); pitch = mix(pitch, STILL_LOOK.pitch, back); yaw = mix(yaw, STILL_LOOK.yaw, back);
    const k = 1 - 0.6 * smooth(seg(t, 6.0, 7.0)), hd = hand(t, k);
    yaw += pt.sx * 3.0 * k + hd.yaw; pitch += -pt.sy * 2.0 * k + hd.pitch;
    pose.pos.copy(pos); pose.yaw = yaw; pose.pitch = pitch; pose.roll = hd.roll;
    pose.zoom = mix(mix(1, 0.84, smooth(seg(t, 5.4, 7.2))), STILL_LOOK.zoom, back);
    return pose;
  };
  const vfov = a => a >= 1 ? 55 : Math.min(80, 2 * Math.atan(Math.tan(27.5 * D2R) / Math.pow(a, 0.62)) / D2R);
  cam.fov = vfov(aspect); cam.updateProjectionMatrix();
  /* the lens, second by second: where the eye focuses and how shallow the field is. Across the room the far things are
     sharp and the desk's edge soft; up at the dome everything is sharp; down to the volume the focus racks to the page and
     the room goes soft; stepping back, the record on the desk is the subject and the room beyond stays a little soft */
  /* where the volume is from the eye: bent over the desk as it is set down and falls open (about 0.85 m), and from the step
     back the still picture is taken from (about 1.45 m); measured from the scene itself, so the page is sharp at the moment the
     shot is about */
  const F_DOWN = bookAt.distanceTo(EYE.clone().addScaledVector(F, 0.24).add(V3(0, -0.12, 0))), F_BACK = bookAt.distanceTo(STILL_POS);
  const lensAt = (t) => {
    if (STILL) return {focus: F_BACK, aper: 0.3};
    const up = sine(seg(t, 1.1, 4.0)), down = sine(seg(t, 5.95, 7.0)), back = sine(seg(t, 8.15, 9.8));      // the focus follows the volume as it is set down
    const toDesk = sine(seg(t, 4.75, 6.3));      // coming down from the dome the eye settles on the desk's edge, then on the volume
    const focus = mix(mix(mix(mix(11, 40, up), 2.2, toDesk), F_DOWN, down), F_BACK, back), aper = mix(mix(mix(mix(0.3, 0.12, up), 0.5, toDesk), 1.0, down), 0.3, back);
    return {focus, aper};
  };

  /* ---------- the veil it comes out of, and the page it fades into (laid on by the lens) ---------- */
  const startCol = new THREE.Color(opts.start || "#0d0a07"), endCol = new THREE.Color(opts.end || "#F6F3EC");
  const lensP = {focus: 10, aper: 0, veil: new THREE.Color(0, 0, 0), veilA: 0, time: 0, beams, expo: 1, sun: U.uSunI.value};

  /* ---------- the volume, second by second ---------- */
  const tmpQ = new THREE.Quaternion(), tmpV = V3();
  const placeBook = (t) => {
    const show = t >= 5.95 || STILL;
    BOOK.grp.visible = show;
    if (!show) return;
    /* carried: up from where your hands are, forward and down onto the desk, a little unsteady until it is down */
    const c = STILL ? 1 : inOut(seg(t, 6.0, 6.95)), u = 1 - c;
    const p0 = handAt, p2 = spineAt, p1 = p0.clone().lerp(p2, 0.55).add(V3(0, 0.12, 0));
    tmpV.copy(p0).multiplyScalar(u * u).addScaledVector(p1, 2 * u * c).addScaledVector(p2, c * c);
    const shake = STILL ? 0 : 0.0025 * (1 - seg(t, 6.7, 7.0));
    tmpV.x += Math.sin(t * 7.3) * shake; tmpV.y += Math.sin(t * 9.1 + 1) * shake * 0.8; tmpV.z += Math.sin(t * 5.7 + 2) * shake;
    const settle = STILL ? 0 : 0.003 * Math.sin(seg(t, 6.95, 7.25) * Math.PI) * (1 - seg(t, 6.95, 7.25));
    tmpV.y += settle;
    BOOK.grp.position.copy(tmpV);
    tmpQ.copy(qHand).slerp(qFlat, smooth(seg(t, 6.05, 6.9)));
    BOOK.grp.quaternion.copy(STILL ? qFlat : tmpQ);
    /* it falls open: the front cover and half the leaves turn about the spine and settle to the left */
    const open = STILL ? 1 : inOut(seg(t, 7.15, 7.9));
    const th = Math.PI * open;
    /* closed, the left half lies upside down on the right: turned by pi about the spine's middle; it swings up and over */
    BOOK.left.g.position.set(0, BK.b + BK.T / 2, 0);
    BOOK.left.g.children.forEach(m => { m.position.set(0, -(BK.b + BK.T / 2), 0); });
    BOOK.left.g.rotation.set(0, 0, th - Math.PI);
    BOOK.shapeBlock(BOOK.left, open); BOOK.shapeBlock(BOOK.right, open);
    BOOK.spine.visible = open < 0.6;
    /* three leaves turn */
    BOOK.leaves.forEach((L, k) => {
      const t0 = 7.95 + k * 0.4, u2 = STILL ? 1 : smooth(seg(t, t0, t0 + 0.78));
      L.g.visible = true;
      BOOK.shapeLeaf(L, u2, k, open);
    });
  };
  /* what is quietly alive whatever the moment: the lamp's filament, the dust's drift, the haze in the shafts */
  const live = (t) => { lamp.intensity = LAMP * (1 + 0.01 * Math.sin(t * 13.1) + 0.004 * Math.sin(t * 37.0)); U.uTime.value = t; lensP.time = t; };

  const frame = (t) => {
    const P = poseAt(t);
    cam.position.copy(P.pos); look(cam, P.yaw, P.pitch, P.roll);
    cam.fov = vfov(cam.aspect) * P.zoom; cam.updateProjectionMatrix();
    placeBook(t); live(t);
    const L = lensAt(t); lensP.focus = L.focus; lensP.aper = L.aper;
    const vin = STILL ? 0 : 1 - smooth(seg(t, 0.05, 1.05)), vout = STILL ? 0 : smooth(seg(t, DUR - 0.6, DUR));
    if (vout > 0) { lensP.veil.copy(endCol); lensP.veilA = vout; } else { lensP.veil.copy(startCol); lensP.veilA = vin; }
    return lensP.veilA;
  };
  /* for the place: the camera set from outside (pos, yaw, pitch, roll, zoom), and the volume lying open on your desk */
  const setView = (p, yaw, pitch, roll = 0, zoom = 1) => { cam.position.copy(p); look(cam, yaw, pitch, roll); cam.fov = vfov(cam.aspect) * zoom; cam.updateProjectionMatrix(); };
  const openBook = () => { placeBook(DUR); BOOK.grp.visible = true; };
  /* where the eye's ray meets the room, for the lens's focus: the floor, a desk's top, the central desk, the walls, the
     dome, whichever comes first */
  const focusAt = (floorY = 0) => {
    const o = cam.position, d = V3(0, 0, -1).applyQuaternion(cam.quaternion);
    let best = 60;
    const hit = t => { if (t > 0.05 && t < best) best = t; };
    if (d.y < -1e-4) {
      hit((floorY - o.y) / d.y);
      const t = (LAY.top - o.y) / d.y;
      if (t > 0) { const x = o.x + d.x * t, z = o.z + d.z * t, r = Math.hypot(x, z), az = Math.atan2(z, x);
        for (const ring of WALK.rings) { if (Math.abs(r - ring.rc) > ring.half - 0.4) continue; const sc = Math.round((az - 22.5 * D2R) / (45 * D2R)) * 45 * D2R + 22.5 * D2R; if (Math.abs(wrapA(az - sc)) < ring.ang) hit(t); } }
      const tc = (1.03 - o.y) / d.y; if (tc > 0 && Math.hypot(o.x + d.x * tc, o.z + d.z * tc) < 4.45) hit(tc);
    }
    for (let i = 0; i < 8; i++) { const a = i * 45 * D2R, nx = Math.cos(a), nz = Math.sin(a), den = nx * d.x + nz * d.z; if (den > 1e-5) hit((ROOM.Rs * FT - (nx * o.x + nz * o.z)) / den); }
    { const cy = ROOM.Hd * FT, R = ROOM.Rd * FT, oy = o.y - cy, bq = 2 * (o.x * d.x + oy * d.y + o.z * d.z), cq = o.x * o.x + oy * oy + o.z * o.z - R * R, disc = bq * bq - 4 * cq;
      if (disc > 0) { const t = (-bq + Math.sqrt(disc)) / 2; if (o.y + d.y * t > ROOM.Ue1 * FT) hit(t); } }
    { const a = d.x * d.x + d.z * d.z, bq = 2 * (o.x * d.x + o.z * d.z), cq = o.x * o.x + o.z * o.z - 4.42 * 4.42, disc = bq * bq - 4 * a * cq;      // the counter's drum
      if (a > 1e-6 && disc > 0 && cq > 0) { const t = (-bq - Math.sqrt(disc)) / (2 * a); if (t > 0 && o.y + d.y * t < 1.05) hit(t); } }
    return best;
  };
  const dispose = () => { scene.traverse(o => { if (o.geometry) o.geometry.dispose(); const ms = o.material ? (Array.isArray(o.material) ? o.material : [o.material]) : [];
    for (const m of ms) { for (const k in m) if (m[k] && m[k].isTexture) m[k].dispose(); if (m.uniforms) for (const k in m.uniforms) { const v = m.uniforms[k].value; if (v && v.isTexture) v.dispose(); } m.dispose(); } });
    rt.dispose(); envRT.dispose(); if (room) { try { pmrem.dispose(); cubeRT.dispose(); } catch (e) {} } };
  /* the room's light taken again from a new place (the place's seats): nothing that moves is in the picture */
  const probe = (p) => {
    if (!room) return;
    cubeCam.position.copy(p);
    const vb = BOOK.grp.visible, vd = dust.visible, auto = renderer.shadowMap.autoUpdate;
    BOOK.grp.visible = false; dust.visible = false; renderer.shadowMap.autoUpdate = false;
    cubeCam.update(renderer, scene); pmrem.fromCubemap(cubeRT.texture, envRT);
    renderer.shadowMap.autoUpdate = auto; BOOK.grp.visible = vb; dust.visible = vd;
  };
  /* Ready to draw: the big pictures sent to the GPU, the shaders compiled (in parallel where the browser can), and the
     room's light taken from where you stand */
  let gpuDone = null;
  const gpu = (isLive = () => false) => gpuDone || (gpuDone = (async () => {
    for (const t of [wallsTex, domeTex]) renderer.initTexture(t);
    mark("upload");
    /* the shaders as the room's picture is drawn (into a render target, without tone mapping) and as the screen is */
    if (renderer.compileAsync) { try { renderer.setRenderTarget(cubeRT, 0); const a = renderer.compileAsync(scene, cubeCam.children[0]);
      renderer.setRenderTarget(null); await Promise.all([a, renderer.compileAsync(scene, cam)]); } catch (e) { renderer.setRenderTarget(null); } }
    mark("compile");
    BOOK.grp.visible = false; dust.visible = false; renderer.shadowMap.autoUpdate = false;      // nothing in the picture of the room needs the lamp's shadows
    if (opts.probeAt) cubeCam.position.copy(opts.probeAt);
    cubeCam.update(renderer, scene); pmrem.fromCubemap(cubeRT.texture, envRT);
    if (!room) { pmrem.dispose(); cubeRT.dispose(); }
    dust.visible = true; renderer.shadowMap.autoUpdate = true; renderer.shadowMap.needsUpdate = true;
    /* one picture drawn unseen with the volume in it, so the lamp's shadow is ready before the volume appears */
    if (!isLive()) { frame(STILL_T); renderer.render(scene, cam); }
    mark("light");
  })());
  mark("end");
  return {scene, cam, frame, dispose, wallsMat, poseAt, marks, gpu, book: BOOK, bookAt, lensP, seats, setView, openBook, live, focusAt, probe, dust, U, vfov,
          handoff(t){ const P = poseAt(t); return {pos: [P.pos.x, P.pos.y, P.pos.z], yaw: P.yaw, pitch: P.pitch, t, at: Date.now()}; },
          resize(a){ cam.aspect = a; cam.fov = vfov(a); cam.updateProjectionMatrix(); }};
}
/* a camera turned to look toward an azimuth (degrees: 0 east, + toward the south) and up by a pitch */
function look(cam, yaw, pitch, roll){ cam.rotation.set(pitch * D2R, -(yaw + 90) * D2R, roll * D2R, "YXZ"); }

function setup(renderer, w, h, ratio){
  renderer.setPixelRatio(ratio); renderer.setSize(w, h, false);
  renderer.outputColorSpace = THREE.SRGBColorSpace; renderer.toneMapping = THREE.NoToneMapping; renderer.toneMappingExposure = 1.0;      // the lens does the tone mapping
}
/* the lens sized to the canvas's own pixels */
function lensFor(renderer, lean, opts){ const L = new Lens(renderer, lean, opts), v = new THREE.Vector2(); renderer.getDrawingBufferSize(v); L.size(v.x, v.y); return L; }
const pixelRatio = (w, h, lean, room) => lean ? Math.min(1.5, devicePixelRatio || 1, Math.sqrt(1.1e6 / (w * h))) : Math.min(2, devicePixelRatio || 1, Math.sqrt((room ? 3.6e6 : 3.9e6) / (w * h)));

/* ================================ playing it over the page ================================ */
const ARRIVE = "tca.record.arrive", STAY = "tca.record.stay";
function leave(url, how){ try { sessionStorage.setItem(ARRIVE, how); } catch (e) {} location.href = url; }
/* opts.stay: the reading room's own page; a Stay button on the veil (any element with data-stay) calls the returned
   controller's stay(), which hands this view over to that page (sessionStorage, this tab only) and goes there, with no
   fade into the record. opts.hold(): true while the reader reaches for Stay (the end waits a little). opts.keys false:
   the caller listens for keys itself. Returns {skip, stay} (false when it cannot be drawn). */
export function run(url, opts = {}){
  if (!supported() || !opts.assets) return false;
  let renderer;
  try { renderer = new THREE.WebGLRenderer({antialias: false, powerPreference: "high-performance"}); } catch (e) { return false; }
  const host = opts.host || document.body.appendChild(document.createElement("div"));
  const w = innerWidth, h = innerHeight, lean = !!(opts.lean || opts.assets.lean);
  setup(renderer, w, h, pixelRatio(w, h, lean, false));
  let S, lens;
  try { S = build(renderer, w / h, Object.assign({}, opts.assets, {lean: opts.assets.lean}), {still: !!opts.still, start: opts.start, end: opts.end}); lens = lensFor(renderer, lean); }
  catch (e) { renderer.dispose(); return false; }
  const cv = renderer.domElement; cv.setAttribute("aria-hidden", "true"); cv.style.cssText = "position:absolute;inset:0;display:block;width:100%;height:100%;opacity:0;transition:opacity .45s ease";
  host.prepend(cv);
  let gone = false, dead = false, t0 = 0, raf = 0, tNow = 0, tEnd = DUR;
  const begun = performance.now(), timers = [], later = (f, ms) => { timers.push(setTimeout(f, ms)); };
  const stop = () => { gone = true; cancelAnimationFrame(raf); for (const id of timers) clearTimeout(id); };
  const go = (how) => { if (gone) return; stop(); leave(url, how); };
  const skip = () => go("skip");
  /* Stay here: the room's own page, this view handed over (this tab only) */
  const stay = () => {
    if (gone || !opts.stay) return;
    stop();
    try { sessionStorage.setItem(STAY, JSON.stringify(S.handoff(opts.still ? STILL_T : tNow))); } catch (e) {}
    cv.style.transition = "opacity .3s ease"; cv.style.opacity = 0;
    setTimeout(() => { if (!dead) location.href = opts.stay; }, 300);
  };
  const onStay = e => !!(e.target && e.target.closest && e.target.closest("[data-stay]"));
  const ac = new AbortController(), signal = ac.signal;
  host.addEventListener("pointerdown", e => { if (onStay(e)) return; if (e.button === 0 || e.pointerType !== "mouse") skip(); });
  host.addEventListener("click", e => { if (!onStay(e)) skip(); });
  if (opts.keys !== false) addEventListener("keydown", e => { if (!quietKey(e)) { e.preventDefault(); skip(); } }, {capture: true, signal});
  addEventListener("resize", () => { renderer.setSize(innerWidth, innerHeight, false); S.resize(innerWidth / innerHeight); const v = new THREE.Vector2(); renderer.getDrawingBufferSize(v); lens.size(v.x, v.y); }, {signal});
  /* Back while it plays keeps this page in the browser's memory with its clocks stopped: when it comes back, the room is
     gone and nothing goes on to the record by itself */
  addEventListener("pagehide", e => { if (e.persisted) stop(); }, {signal});
  addEventListener("pageshow", e => { if (e.persisted) { stop(); dead = true; ac.abort(); host.remove(); try { S.dispose(); lens.dispose(); renderer.dispose(); } catch (x) {} } }, {signal});
  if (opts.onStart) opts.onStart();
  const holding = () => { try { return !!(opts.hold && opts.hold()); } catch (e) { return false; } };
  const draw = t => { S.frame(t); lens.render(S.scene, S.cam, S.lensP); };
  let started = false;
  const tick = now => {
    if (gone) return;
    if (!t0) t0 = now;
    const t = (now - t0) / 1000;
    if (holding() && t > tEnd - 1.4 && tEnd < DUR + 6) tEnd = Math.min(DUR + 6, t + 1.4);      // reaching for Stay: the room waits a little
    tNow = Math.min(t, tEnd);
    pt.sx += (pt.x - pt.sx) * 0.05; pt.sy += (pt.y - pt.sy) * 0.05;
    draw(Math.min(DUR, tNow));
    if (t < tEnd) raf = requestAnimationFrame(tick); else go("full");
  };
  const start = () => {
    if (started || gone) return;
    started = true;
    if (opts.still) {      // motion off, Calm, or reduced motion: one still picture, then a plain fade (it waits while the reader reaches for Stay)
      draw(STILL_T); cv.style.transition = "none"; cv.style.opacity = 1;
      const end = () => { if (gone) return; if (holding() && performance.now() - begun < 9000) { later(end, 250); return; } if (opts.fade) opts.fade(); later(() => go("still"), 420); };
      later(end, 1700);
      return;
    }
    draw(0);
    requestAnimationFrame(() => { cv.style.opacity = 1; });
    raf = requestAnimationFrame(tick);
    const guard = () => { if (gone) return; if (performance.now() - begun < (tEnd + 1.8) * 1000) { later(guard, 400); return; } go("full"); };
    later(guard, DUR * 1000 + 1800);      // a window that is not drawing frames still gets there
  };
  S.gpu(() => started).then(start, start);
  later(start, 3000);      // never kept waiting
  return {skip, stay};
}
/* keys that skip nothing: a modifier, a lock or a screen reader's own key pressed alone (Ctrl also stops speech), and any
   key pressed with Ctrl, Alt or the command key, which belongs to the browser */
const QUIET = ["Shift", "Control", "Alt", "AltGraph", "Meta", "OS", "Super", "Hyper", "Fn", "FnLock", "CapsLock", "NumLock", "ScrollLock", "Insert", "Unidentified", "Process"];
function quietKey(e){ return e.ctrlKey || e.metaKey || e.altKey || QUIET.includes(e.key); }

/* ================================ the reading room, to sit in ================================ */
/* The place (John, 2026-10-11): the reader starts seated in the seat they picked and looks around by dragging, by touch
   or with the arrow keys; a button gets them up to walk (W A S D or the arrows on a computer; on a phone, a button held
   to walk the way they look); nothing walks through a wall or a desk; a seat is one tap away again. Sound is off until
   the reader turns it on. With motion off it is one still picture that still turns with a drag or a key.
     enter(canvas, {assets: from prepareRoom(), seat, from (a crossing's handoff), still, lean, sound: false,
                    keysOK(e), onReady(info), onInput(kind), onLook(facing), onMove(state), onLost()})
   returns a controller: stop(), seat(id), stand(), sit(), setStill(on), setSound(on), facing(), state(), look(yaw, pitch),
   walkHold(on) (the phone's button), redraw(), seats, and t. */
export function enter(canvas, opts = {}){
  if (!canvas || !opts.assets || !supported()) return null;
  let renderer;
  try { renderer = new THREE.WebGLRenderer({canvas, antialias: false, powerPreference: opts.lean ? "low-power" : "high-performance", preserveDrawingBuffer: !!opts.keep}); } catch (e) { return null; }
  const lean = !!opts.lean, ac = new AbortController(), on = (el, ev, fn, o) => el.addEventListener(ev, fn, Object.assign({signal: ac.signal}, o || {}));
  const dims = () => { const r = canvas.getBoundingClientRect(); return [Math.max(1, Math.round(r.width || innerWidth)), Math.max(1, Math.round(r.height || innerHeight))]; };
  let [w, h] = dims();
  setup(renderer, w, h, pixelRatio(w, h, lean, true));
  const A = Object.assign({}, opts.assets, {room: true});
  const seat0 = SEATS.some(x => x.id === opts.seat) ? opts.seat : "desk";
  let S, lens;
  try {
    S = build(renderer, w / h, A, {still: true, room: true, probeAt: V3()});
    lens = lensFor(renderer, lean);
  } catch (e) { console.warn("The reading room could not be drawn:", e); renderer.dispose(); return null; }
  S.openBook();
  const seats = S.seats, sound = new RoomSound();
  /* the reader: where they are, which way they look, seated or on foot */
  const me = {pos: V3(), yaw: 0, pitch: 0, floor: 0, seat: seat0, mode: "seated", eye: SEATS[0].eye, bob: 0, phase: 0, vel: V3()};
  const place = (id) => { const s = seats[id]; me.pos.copy(s.pos); me.yaw = s.yaw; me.pitch = s.pitch; me.floor = s.floor; me.seat = id; me.mode = "seated"; me.eye = s.eye; };
  place(seat0);
  /* a view handed over by the crossing (this tab only, within two minutes): start on foot at that very spot, then the
     reader can sit */
  const f = opts.from;
  if (f && Array.isArray(f.pos) && f.pos.length === 3 && f.pos.every(Number.isFinite) && isFinite(f.yaw) && isFinite(f.pitch) && isFinite(f.at) && Math.abs(Date.now() - f.at) < 120000) {
    me.pos.set(f.pos[0], STAND_EYE, f.pos[2]); me.yaw = f.yaw; me.pitch = clamp(f.pitch, -80, 80); me.mode = "walking"; me.eye = STAND_EYE; me.floor = 0;
    if (!floorOK(me.pos.x, me.pos.z)) { const u = seats.desk.up; me.pos.copy(u); }
  }
  let still = !!opts.still, alive = true, raf = 0, t0 = performance.now(), last = t0, drawn = 0, settleT = 0, veilA = 0, veilTo = 0, focus = 4, probedAt = V3(1e9, 0, 0);
  const lensP = S.lensP; lensP.veil.set(0, 0, 0); lensP.aper = lean ? 0 : 0.15;
  const tNow = () => (performance.now() - t0) / 1000;
  /* the move between seats: a fade down, the move, a fade up (a cut, as a film cuts) */
  let cut = null;
  const cutTo = (fn) => { if (cut) return; cut = {t: tNow(), fn}; poke(); };
  /* getting up: the eyes rise from the seat to standing over a second and a quarter, a half-step back from the desk */
  let rising = null;
  const standUp = () => {
    if (me.mode !== "seated" || rising) return;
    const s = seats[me.seat], from = s.pos.clone(), to = s.up.clone();
    if (still) {      // a still picture: on your feet at once, nothing moves
      me.pos.copy(to); me.eye = STAND_EYE; me.pitch = clamp(me.pitch * 0.6, -30, 30); me.mode = "walking"; sound.place(me.seat, true); reprobe(true);
      if (opts.onMove) opts.onMove(state()); poke(); return;
    }
    rising = {t: tNow(), from, to, dir: 1, yaw0: me.yaw, pitch0: me.pitch, pitch1: clamp(me.pitch * 0.6, -30, 30)};
    me.mode = "walking"; sound.place(me.seat, true); if (opts.onMove) opts.onMove(state()); poke();
  };
  const sitDown = (id) => {
    const want = id && seats[id] ? id : nearestSeat();
    const s = seats[want];
    if (me.mode === "walking" && !rising && me.pos.distanceTo(s.up) < 1.6 && Math.abs(me.pos.y - s.up.y) < 0.5) {      // close by: sit, no cut
      if (still) { place(want); me.eye = s.eye; sound.place(want, false); reprobe(true); if (opts.onMove) opts.onMove(state()); poke(); return; }      // at once
      rising = {t: tNow(), from: me.pos.clone(), to: s.pos.clone(), dir: -1, yaw0: me.yaw, pitch0: me.pitch, pitch1: s.pitch, seat: want};
      me.seat = want; poke(); return;
    }
    cutTo(() => { place(want); me.eye = s.eye; sound.place(want, false); reprobe(true); if (opts.onMove) opts.onMove(state()); });
  };
  const nearestSeat = () => { let best = "desk", bd = 1e9; for (const id in seats) { const d = me.pos.distanceTo(seats[id].up); if (d < bd) { bd = d; best = id; } } return best; };
  const reprobe = (force) => { if (force || me.pos.distanceTo(probedAt) > 3.5) { probedAt.copy(me.pos); S.probe(me.pos); } };
  /* looking around: drag (a mouse, a finger, a pen), with a little glide after a quick drag; the arrow keys turn the head
     when seated, and on foot the arrows and W A S D walk */
  const kdeg = () => S.cam.fov / Math.max(1, h);
  let drag = null; const inertia = {y: 0, p: 0}, held = new Set();
  let walkHeld = false;
  /* in the visitors' gallery (the west alcove's upper room) the photograph was taken looking into the room, so to either side
     and behind there is only a neighbouring bay's wall stretched over the alcove's: the look stays within the window the
     photograph covers, and a drag's glide stops at its edge */
  const GAL_LOOK = {yaw: 58, lo: -48, hi: 62};
  const wrapDeg = a => { a = (a + 180) % 360; if (a < 0) a += 360; return a - 180; };
  const limitLook = () => {
    if (me.floor <= 0) return;
    const c = seats.gallery.yaw, d = wrapDeg(me.yaw - c);
    if (d > GAL_LOOK.yaw) { me.yaw = c + GAL_LOOK.yaw; if (inertia.y > 0) inertia.y = 0; }
    else if (d < -GAL_LOOK.yaw) { me.yaw = c - GAL_LOOK.yaw; if (inertia.y < 0) inertia.y = 0; }
    else me.yaw = c + d;
    if (me.pitch > GAL_LOOK.hi) { me.pitch = GAL_LOOK.hi; if (inertia.p > 0) inertia.p = 0; }
    else if (me.pitch < GAL_LOOK.lo) { me.pitch = GAL_LOOK.lo; if (inertia.p < 0) inertia.p = 0; }
  };
  const turnBy = (dy, dp) => { me.yaw += dy; me.pitch = clamp(me.pitch + dp, -85, 85); limitLook(); };
  const said = () => { clearTimeout(settleT); settleT = setTimeout(() => { if (opts.onLook) opts.onLook(facing()); }, 650); };
  on(canvas, "pointerdown", e => {
    if (drag || (e.pointerType === "mouse" && e.button !== 0)) return;
    drag = {id: e.pointerId, x: e.clientX, y: e.clientY, s: []}; inertia.y = inertia.p = 0;
    canvas.classList.add("dragging"); if (opts.onInput) opts.onInput("drag");
  });
  on(window, "pointermove", e => {
    if (!drag || e.pointerId !== drag.id) return;
    const kk = kdeg(), dy = (e.clientX - drag.x) * kk, dp = (e.clientY - drag.y) * kk;
    drag.x = e.clientX; drag.y = e.clientY; turnBy(dy, dp);
    drag.s.push([performance.now(), dy, dp]); if (drag.s.length > 8) drag.s.shift();
    poke();
  }, {passive: true});
  const endDrag = e => {
    if (!drag || (e && e.pointerId != null && e.pointerId !== drag.id)) return;
    const now = performance.now(), sm = drag.s.filter(q => now - q[0] < 90);
    if (!still && sm.length >= 2) { const span = Math.max(0.03, (now - sm[0][0]) / 1000); inertia.y = clamp(sm.reduce((a, q) => a + q[1], 0) / span, -240, 240); inertia.p = clamp(sm.reduce((a, q) => a + q[2], 0) / span, -160, 160); }
    drag = null; canvas.classList.remove("dragging"); poke(); said();
  };
  on(window, "pointerup", endDrag); on(window, "pointercancel", endDrag);
  on(window, "blur", () => { endDrag(); held.clear(); walkHeld = false; });
  const KEYS = {ArrowLeft: "left", ArrowRight: "right", ArrowUp: "up", ArrowDown: "down", w: "fwd", W: "fwd", s: "back", S: "back", a: "strafeL", A: "strafeL", d: "strafeR", D: "strafeR"};
  on(window, "keydown", e => {
    const k = KEYS[e.key];
    if (!k || e.altKey || e.ctrlKey || e.metaKey || (opts.keysOK && !opts.keysOK(e))) return;
    if (me.mode === "seated" && (k === "fwd" || k === "back" || k === "strafeL" || k === "strafeR")) return;      // the letters only walk
    e.preventDefault(); if (opts.onInput) opts.onInput("key");
    if (still && me.mode === "seated") { turnBy(k === "left" ? -6 : k === "right" ? 6 : 0, k === "up" ? 4 : k === "down" ? -4 : 0); poke(); said(); return; }
    held.add(k); poke();
  });
  on(window, "keyup", e => { const k = KEYS[e.key]; if (k && held.delete(k)) { poke(); said(); } });
  /* a step on foot: the floor's rules, tried whole and then along each axis */
  const tryMove = (dx, dz) => {
    const ok = me.floor > 0 ? galleryOK : floorOK;
    if (ok(me.pos.x + dx, me.pos.z + dz)) { me.pos.x += dx; me.pos.z += dz; return true; }
    let moved = false;
    if (dx && ok(me.pos.x + dx, me.pos.z)) { me.pos.x += dx; moved = true; }
    if (dz && ok(me.pos.x, me.pos.z + dz)) { me.pos.z += dz; moved = true; }
    return moved;
  };
  const step = dt => {
    let moving = !!drag;
    const sp = (a, b) => held.has(a) ? 1 : held.has(b) ? -1 : 0;
    if (me.mode === "seated") {
      if (held.size) { turnBy(sp("right", "left") * 62 * dt, sp("up", "down") * 40 * dt); moving = true; }
    } else if (!rising) {
      const turn = sp("right", "left"), look = sp("up", "down"), fwd = (held.has("fwd") || walkHeld ? 1 : 0) - (held.has("back") ? 1 : 0), side = sp("strafeR", "strafeL");
      if (turn || look) { turnBy(turn * 70 * dt, look * 40 * dt); moving = true; }
      /* on foot: the arrows alone turn and look; with W or the walk button held, forward is the way you look */
      const want = V3(), fdir = dirAz(me.yaw), rdir = V3(-fdir.z, 0, fdir.x);
      want.addScaledVector(fdir, fwd).addScaledVector(rdir, side);
      if (want.lengthSq() > 0) want.normalize().multiplyScalar(WALK_SPEED);
      me.vel.lerp(want, 1 - Math.exp(-dt / 0.18));      // weight: a person gets going and stops over a fifth of a second
      if (me.vel.lengthSq() > 1e-4) {
        const moved = tryMove(me.vel.x * dt, me.vel.z * dt);
        if (!moved) me.vel.multiplyScalar(0.5);
        const v = me.vel.length(), ph0 = me.phase;
        me.phase += dt * v * 1.75;      // steps: about 1.75 a second at walking pace
        if (Math.floor(me.phase) !== Math.floor(ph0)) sound.ownStep();
        me.bob = Math.min(1, v / WALK_SPEED);
        moving = true; reprobe(false);
      } else { me.bob *= Math.exp(-dt / 0.3); }
    }
    if (!drag && (Math.abs(inertia.y) > 0.6 || Math.abs(inertia.p) > 0.6)) {
      turnBy(inertia.y * dt, inertia.p * dt); const q = Math.exp(-dt / 0.32); inertia.y *= q; inertia.p *= q; moving = true;
      if (Math.abs(inertia.y) <= 0.6 && Math.abs(inertia.p) <= 0.6) said();
    } else if (!drag) inertia.y = inertia.p = 0;
    return moving;
  };
  /* the eyes, this frame: the seat or the walk, the rise between them, the breath, the step's bob, the head's small
     unsteadiness, then the lens's focus racking toward what the eyes are on */
  const eyes = (t, dt) => {
    const p = V3().copy(me.pos);
    let yaw = me.yaw, pitch = me.pitch, roll = 0;
    if (rising) {
      const u = inOut(clamp((t - rising.t) / 1.25));
      p.copy(rising.from).lerp(rising.to, u); p.y += Math.sin(u * Math.PI) * 0.03 * rising.dir;
      pitch = mix(rising.pitch0, rising.pitch1, u); me.pitch = pitch;
      if (u >= 1) { if (rising.dir < 0) { place(rising.seat); sound.place(me.seat, false); reprobe(true); } else { me.pos.copy(rising.to); me.eye = STAND_EYE; }
        rising = null; if (opts.onMove) opts.onMove(state()); }
      else me.pos.copy(p);
    }
    if (me.mode === "seated") { p.y = me.floor + me.eye + 0.004 * Math.sin(t * 1.35); yaw += 0.05 * Math.sin(t * 0.41); pitch += 0.04 * Math.sin(t * 0.37 + 1); }
    else if (!rising) { p.y = me.floor + STAND_EYE + 0.006 * Math.sin(t * 1.35) + me.bob * 0.022 * Math.sin(me.phase * Math.PI * 2); roll = me.bob * 0.35 * Math.sin(me.phase * Math.PI); yaw += me.bob * 0.25 * Math.sin(me.phase * Math.PI); }
    if (!still) { yaw += 0.06 * Math.sin(t * 0.53 + 1.3) + 0.02 * Math.sin(t * 1.71); pitch += 0.05 * Math.sin(t * 0.47) + 0.015 * Math.sin(t * 1.45); roll += 0.05 * Math.sin(t * 0.33); }
    S.setView(p, yaw, pitch, roll, 1);
    let want = S.focusAt(me.floor); if (want > 1.4 && want < 3.2) want = 3.2;      // the eye settles on the room unless it is plainly on the desk
    focus += (want - focus) * (1 - Math.exp(-dt / 0.45));
    lensP.focus = focus; lensP.aper = lean ? 0 : (me.mode === "seated" ? 0.15 : 0.12);
  };
  const draw = (t, dt) => {
    eyes(t, dt); S.live(t);
    if (cut) { const u = (t - cut.t); if (u < 0.32) veilA = u / 0.32; else if (cut.fn) { cut.fn(); cut.fn = null; veilA = 1; } else veilA = Math.max(0, 1 - (u - 0.4) / 0.6); if (u > 1.0) cut = null; }
    else veilA = 0;
    lensP.veilA = veilA;
    lens.render(S.scene, S.cam, lensP);
  };
  const tick = now => {
    raf = 0; if (!alive) return;
    const dt = Math.min(0.1, Math.max(0, (now - last) / 1000)); last = now;
    const moving = step(dt), t = tNow();
    if (still) { draw(t, dt); drawn = now; if (cut || rising) raf = requestAnimationFrame(tick); return; }      // a still picture is drawn again only when the reader turns it, or moves seat
    const busy = moving || !!rising || !!cut, gapMs = busy ? (lean ? 31 : 0) : (lean ? 48 : 31);
    if (now - drawn >= gapMs) { drawn = now; draw(t, dt); }
    raf = requestAnimationFrame(tick);
  };
  const poke = () => { if (!raf && alive) raf = requestAnimationFrame(tick); };
  const resize = () => { [w, h] = dims(); renderer.setPixelRatio(pixelRatio(w, h, lean, true)); renderer.setSize(w, h, false); S.resize(w / h); const v = new THREE.Vector2(); renderer.getDrawingBufferSize(v); lens.size(v.x, v.y); poke(); };
  on(window, "resize", resize); if (window.visualViewport) on(window.visualViewport, "resize", resize);
  on(canvas, "webglcontextlost", e => { e.preventDefault(); ctl.stop(); if (opts.onLost) opts.onLost(); });
  on(window, "pagehide", e => { if (e.persisted) { alive = false; if (raf) cancelAnimationFrame(raf); raf = 0; sound.pause(); } else ctl.stop(); });
  on(window, "pageshow", e => { if (e.persisted && !alive) { alive = true; last = performance.now(); sound.resume(); poke(); } });
  on(document, "visibilitychange", () => { if (document.hidden) sound.pause(); else sound.resume(); });
  const facing = () => ({yaw: ((me.yaw % 360) + 360) % 360, pitch: me.pitch, az: ((me.yaw % 360) + 360) % 360});
  const state = () => ({seat: me.mode === "seated" ? me.seat : null, mode: me.mode, near: me.mode === "walking" ? nearestSeat() : me.seat, gallery: me.floor > 0,
                        pos: [+me.pos.x.toFixed(2), +me.pos.y.toFixed(2), +me.pos.z.toFixed(2)]});
  /* ready: the pictures sent to the GPU, the shaders compiled, the light taken from the seat, the first frame drawn */
  let ready = false;
  S.gpu(() => true).then(() => { S.probe(me.pos); probedAt.copy(me.pos); draw(0, 0); drawn = performance.now(); ready = true; if (opts.onReady) opts.onReady({seats: SEATS, state: state()}); if (!still) poke(); },
    e => { console.warn("The reading room could not be drawn:", e); if (opts.onLost) opts.onLost(); });
  const ctl = {
    stop(){ if (!ac.signal.aborted) { alive = false; if (raf) cancelAnimationFrame(raf); raf = 0; clearTimeout(settleT); ac.abort(); sound.close(); S.dispose(); lens.dispose(); renderer.dispose(); } },
    seat(id){ if (!seats[id]) return; if (me.mode === "seated" && me.seat === id && !rising) return; sitDown(id); },
    stand(){ standUp(); },
    sit(){ sitDown(null); },
    setStill(v){ still = !!v; inertia.y = inertia.p = 0; held.clear(); poke(); },
    setSound(v){ if (v) sound.start(); else sound.stop(); sound.place(me.mode === "seated" ? me.seat : nearestSeat(), me.mode !== "seated"); },
    soundOn: () => sound.on,
    walkHold(v){ walkHeld = !!v; poke(); },
    look(yaw, pitch){ me.yaw = yaw; me.pitch = clamp(pitch, -85, 85); limitLook(); poke(); },
    facing, state, seats: SEATS, get t(){ return tNow(); }, get ready(){ return ready; },
    redraw: () => poke(), scene: S.scene
  };
  return ctl;
}

/* one frame, for checking: at second t of the crossing; opts.pose {pos, yaw, pitch, fov} looks from anywhere instead,
   opts.still draws the still picture, opts.debug 1 or 2 shows where the walls found their colour; opts.room draws the
   place instead (its own files), from opts.seat ("desk", "gallery", "centre") or opts.walk {pos, yaw, pitch} (standing),
   with opts.look {yaw, pitch} turning the head; opts.sun scales the shafts (0 for none) */
export async function still(t = STILL_T, w = 960, h = 540, opts = {}){
  const A = opts.room ? await prepareRoom(opts) : await prepare(opts);
  if (opts.pt) { pt.x = pt.sx = opts.pt.x; pt.y = pt.sy = opts.pt.y; }
  const renderer = new THREE.WebGLRenderer({antialias: false, preserveDrawingBuffer: true});
  setup(renderer, w, h, 1);
  const lean = !!(opts.lean || A.lean);
  const S = build(renderer, w / h, A, Object.assign({}, opts, {still: !!opts.still || !!opts.room, room: !!opts.room}));
  const lens = lensFor(renderer, lean, {dof: opts.dof});
  await S.gpu();
  let v;
  if (opts.room) {
    S.openBook(); S.live(opts.time || 3);
    const seat = S.seats[opts.seat] || S.seats.desk;
    let p = seat.pos.clone(), yaw = seat.yaw, pitch = seat.pitch, floor = seat.floor;
    if (opts.walk) { p = V3(...opts.walk.pos); yaw = opts.walk.yaw; pitch = opts.walk.pitch; floor = opts.walk.floor || 0; }
    if (opts.look) { yaw = opts.look.yaw != null ? opts.look.yaw : yaw; pitch = opts.look.pitch != null ? opts.look.pitch : pitch; }
    S.probe(p); S.setView(p, yaw, pitch, 0, 1);
    { let f = S.focusAt(floor); if (f > 1.4 && f < 3.2) f = 3.2; S.lensP.focus = f; } S.lensP.aper = lean ? 0 : (opts.walk ? 0.12 : 0.15); S.lensP.veilA = 0;
    v = 0;
  } else v = S.frame(t);
  const t1 = performance.now();
  if (opts.pose) { S.cam.position.set(...opts.pose.pos); look(S.cam, opts.pose.yaw, opts.pose.pitch, 0); if (opts.pose.fov) { S.cam.fov = opts.pose.fov; S.cam.updateProjectionMatrix(); } }
  if (opts.debug) S.wallsMat.uniforms.uDebug.value = opts.debug;
  if (opts.inspect) opts.inspect(S, THREE, lens);
  if (opts.noLens) renderer.render(S.scene, S.cam); else lens.render(S.scene, S.cam, S.lensP);
  const gl = renderer.getContext(); gl.readPixels(0, 0, 1, 1, gl.RGBA, gl.UNSIGNED_BYTE, new Uint8Array(4));
  const t2 = performance.now(), url = renderer.domElement.toDataURL(opts.png ? "image/png" : "image/jpeg", 0.9);
  const m = S.marks, times = m.slice(1).map((x, i) => x[0] + " " + Math.round(x[1] - m[i][1])).join(", ") + ", first frame " + Math.round(t2 - t1);
  const info = {focus: +S.lensP.focus.toFixed(2), aper: S.lensP.aper, hdr: lens.hdr, samples: lens.samples, hi: !!A.hi, kw: A.kw, size: [renderer.domElement.width, renderer.domElement.height]};
  S.dispose(); lens.dispose(); renderer.dispose(); renderer.forceContextLoss();
  return {url, veil: v, times, info};
}
