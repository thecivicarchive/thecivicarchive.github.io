/*
  The Civic Archive companion: the tabby cat (Felis catus), a brown mackerel tabby, sitting upright.

  Built on the companions' realism kit (kit.js) from the proportions, joint ranges, gaits and habits in
  research/cat.md (Day & Jayne 2007 for the limbs; Vidal, Graf & Berthoz 1986 for the vertical neck and the head
  carried 5 degrees up; Guitton 1984 for eyes that move only 25 degrees so the head turns; Populin & Yin 1998 for ears
  that swivel 25 ms before the head; Gruart 1995 for blinks that close ten times faster than they open; Humphrey 2020 for
  the slow blink; Cafazzo & Natoli 2009 for the tail-up greeting; Leyhausen 1979 for the pre-pounce treading; Muybridge
  plates 716 and 717 for the gathered flight and the tail flagged up at a jump; Walker 1998 for the tail as the body's
  counterweight). No licensed model of a real cat exists without a login (research/cat.md), so the whole animal is
  sculpted here in code as one signed distance field (pelvis, folded hind legs with the knees set just outside the
  forelegs, thorax, a vertical neck, a round skull with a short muzzle and whisker pads, cupped ears with rounded tips,
  straight forelegs standing as two columns, a tail wrapped along the left flank) and surfaced as one mesh that bends over
  a skeleton of 26 bones plus the eyes' own joints; the coat is painted per vertex (agouti ground with ticking, the
  mackerel bars and the dorsal line, rings on the tail and legs, the M on the forehead, eye liner and pale spectacles,
  cheek stripes, a pale muzzle, chin and bib, the pale thumbprint on each ear) and dressed in short fur shells, longer on
  the ruff and the tail; the eyes sit deep in their sockets under lidded, almond openings and are wet, amber, with a
  vertical slit pupil that widens with attention; the nose is moist leather; the whiskers are fine lines that come
  forward when it is curious. Springs give the tail follow-through and a swing against the body's own acceleration (the
  tip fastest), and let the ears and whiskers lag a quick turn of the head. A sitting sculpt cannot swing an upper arm
  far (it lies inside the chest's outline), so the face wash folds the elbow and brings the head down to the paw, as the
  animal does. Nothing is loaded from anywhere.

  export default { id, name, latin, rests, build(THREE, kit) -> rig, update(rig, dt, state), play(rig, clip) -> seconds, rest(rig) }
    rig.root   1 unit = the cat's height sitting (floor to ear tips), facing +z toward the reader, paws at y = 0
    rig.frame  the box, in root units, a camera should keep in view
    clips      arrive (it drops in from above, lands forepaws first and settles into the sit, tail flagged), idleA, idleB
               (tail-tip flick, ears swivelling one at a time, the face wash with a licked paw, settling lower), notice,
               react (the slow blink: the cat's greeting), talk, lookLeft, lookRight, rest, dance (the pounce-play: stare,
               crouch, the rump wiggle, a hop, then the tail-up greeting and a slow blink; or the greeting alone with a
               head bunt). Every clip ends exactly on the rest pose.
*/

function buildCat(THREE, K) {
  if (!K || !K.rig) throw new Error('the cat needs the companions kit: build(THREE, kit)');
  const { sd, surf, rgb, mixc, fbm, noise, sst, lerp, clamp, unit } = K;
  const PI = Math.PI, TAU = 2 * PI;
  const YAW = -0.5, HEAD_YAW = 0.4, FACE = -(YAW + HEAD_YAW);      /* the body sits turned; the head rests nearly facing the reader */
  const R = K.rig({
    id: 'cat', yaw: YAW, frame: { x: [-0.44, 0.5], y: [-0.03, 1.1] }, fov: 34,
    breath: 0.42, blinkSpeed: 1.1, look: { yaw: 0.85, pitch: 0.4, speed: 7.5 },
    idles: ['idleA', 'idleB', 'idleB', 'lookLeft', 'lookRight', 'notice'],
  });

  /* ---------- colours (black, white, greys, browns, buff only) ---------- */
  const BASE = rgb(0x9b7d5b), BASE2 = rgb(0x7a624a), TICK = rgb(0xcbb28e);
  const DARK = rgb(0x2b2219), DARK2 = rgb(0x3e3228), LINER = rgb(0x1a1410);
  const PALE = rgb(0xe9ddc6), PALE2 = rgb(0xcdbc9d);
  const NOSE = rgb(0x8a5f55), NOSE2 = rgb(0x5a3a33), INNER = rgb(0xd6bba7), INNER2 = rgb(0xb79583);

  /* ---------- small vector helpers ---------- */
  const add3 = (a, b) => [a[0] + b[0], a[1] + b[1], a[2] + b[2]];
  const mul3 = (a, k) => [a[0] * k, a[1] * k, a[2] * k];
  const dist3 = (a, b) => Math.hypot(a[0] - b[0], a[1] - b[1], a[2] - b[2]);
  const seg3 = (x, y, z, a, b) => {
    const dx = b[0] - a[0], dy = b[1] - a[1], dz = b[2] - a[2], l2 = dx * dx + dy * dy + dz * dz;
    const t = l2 > 0 ? clamp(((x - a[0]) * dx + (y - a[1]) * dy + (z - a[2]) * dz) / l2, 0, 1) : 0;
    return Math.hypot(x - a[0] - dx * t, y - a[1] - dy * t, z - a[2] - dz * t);
  };
  const along = (P, Q, x, y, z) => { const dx = Q[0] - P[0], dy = Q[1] - P[1], dz = Q[2] - P[2]; return ((x - P[0]) * dx + (y - P[1]) * dy + (z - P[2]) * dz) / (dx * dx + dy * dy + dz * dz); };
  const poly2 = (u, v, pts) => {
    let best = Infinity;
    for (let i = 0; i < pts.length - 1; i++) {
      const a = pts[i], b = pts[i + 1], dx = b[0] - a[0], dy = b[1] - a[1], l2 = dx * dx + dy * dy;
      const t = clamp(((u - a[0]) * dx + (v - a[1]) * dy) / l2, 0, 1);
      best = Math.min(best, Math.hypot(u - a[0] - dx * t, v - a[1] - dy * t));
    }
    return best;
  };
  const band = (d, w, soft = 0.003) => sst(w + soft, w - soft, d);      /* 1 inside a stripe of half-width w, soft-edged */

  /* ---------- landmarks of the sitting cat (sculpting space; the hind limb a third longer than the fore, Day & Jayne) ---------- */
  /* the knees and hind feet sit a little outside the forelegs, so the forelegs stand as their own columns in front of them
     (and a lifted forepaw leaves the knee behind instead of dragging its skin along) */
  const HIP = (s) => [s * 0.13, 0.26, -0.17], STIF = (s) => [s * 0.185, 0.125, 0.105], HOCK = (s) => [s * 0.17, 0.045, -0.13], HTOE = (s) => [s * 0.165, 0.024, 0.04];
  const SJ = (s) => [s * 0.078, 0.555, 0.065], ELB = (s) => [s * 0.083, 0.3, 0.0], WR = (s) => [s * 0.08, 0.095, 0.075], MC = (s) => [s * 0.08, 0.04, 0.135], FTOE = (s) => [s * 0.082, 0.024, 0.19];
  const CP = [0, 0.36, -0.05], NP0 = [0, 0.55, 0.03], NP1 = [0, 0.68, 0.055];
  const HC = [0, 0.775, 0.085];
  const EP = (s) => [s * 0.072, 0.855, 0.03], EROT = (s) => [-0.14, s * 0.35, -s * 0.3];
  const PADC = (s) => [s * 0.025, 0.727, 0.213];
  const T = [[0, 0.12, -0.31], [0.085, 0.06, -0.405], [0.2, 0.038, -0.37], [0.3, 0.034, -0.235], [0.33, 0.03, -0.06], [0.29, 0.028, 0.105], [0.21, 0.026, 0.215]];
  const TR = [0.042, 0.04, 0.037, 0.034, 0.031, 0.027, 0.021];

  /* ---------- the body as fields ---------- */
  const pelvis = sd.egg([0, 0.215, -0.19], [0.17, 0.185, 0.165], [-0.3, 0, 0]);
  const thorax = sd.egg([0, 0.4, -0.03], [0.15, 0.2, 0.15], [-0.22, 0, 0]);
  const sternum = sd.egg([0, 0.44, 0.075], [0.11, 0.15, 0.085]);
  const shoulder = (s) => sd.egg([s * 0.088, 0.565, 0.0], [0.055, 0.075, 0.07]);
  const neckF = sd.limb(NP0, NP1, 0.088, 0.08);
  const thigh = (s) => sd.limb(HIP(s), STIF(s), 0.1, 0.066);
  const shank = (s) => sd.limb(STIF(s), HOCK(s), 0.056, 0.038);
  const hfoot = (s) => sd.add(0.015, sd.limb(HOCK(s), HTOE(s), 0.034, 0.03), sd.egg([s * 0.165, 0.025, 0.085], [0.044, 0.025, 0.06]));
  const arm = (s) => sd.limb(SJ(s), ELB(s), 0.056, 0.044);
  const fore = (s) => sd.limb(ELB(s), WR(s), 0.042, 0.034);
  const paw = (s) => {
    const toes = [];
    for (let i = 0; i < 4; i++) toes.push(sd.egg([s * 0.082 + (i - 1.5) * 0.023, 0.021, 0.205], [0.013, 0.015, 0.022]));
    return sd.add(0.012, sd.limb(WR(s), MC(s), 0.032, 0.03), sd.egg([s * 0.082, 0.027, 0.17], [0.042, 0.03, 0.052]), sd.add(0.006, ...toes));
  };
  /* the head: a round skull, full cheeks, brows over the eyes, a short muzzle with whisker pads and a small chin */
  const skull = sd.egg(HC, [0.117, 0.104, 0.112]);
  const occiput = sd.egg([0, 0.765, 0.02], [0.1, 0.09, 0.09]);
  const cheek = (s) => sd.egg([s * 0.058, 0.745, 0.115], [0.075, 0.068, 0.078]);
  const brow = (s) => sd.egg([s * 0.05, 0.825, 0.145], [0.042, 0.022, 0.035]);
  const muzzle = sd.egg([0, 0.733, 0.185], [0.052, 0.04, 0.05]);
  const pad = (s) => sd.egg(PADC(s), [0.03, 0.026, 0.026]);
  const chin = sd.egg([0, 0.702, 0.182], [0.03, 0.022, 0.03]);
  const headF = sd.add(0.02, sd.add(0.03, skull, occiput, cheek(1), cheek(-1), brow(1), brow(-1)), muzzle, pad(1), pad(-1), chin);
  /* the eyes: set into sockets on the front of the skull, looking a little outward */
  /* the eyeball sits deep in its socket (only the cornea's cap stands proud of the face, as in the real animal, where the
     lids are folds of skin flush with the fur, not a marble on the cheek) */
  const EYE_R = 0.032, EYES = [];
  for (const s of [1, -1]) {
    const py = s * 0.5, pp = 0.04, ly = s * 0.22, lp = 0.03;
    const dp = [Math.sin(py) * Math.cos(pp), Math.sin(pp), Math.cos(py) * Math.cos(pp)];
    const dl = [Math.sin(ly) * Math.cos(lp), Math.sin(lp), Math.cos(ly) * Math.cos(lp)];
    const sp = K.hit(headF, HC, dp), c = add3(sp, mul3(dp, -EYE_R * 0.78));
    EYES.push({ s, c, dl, sp });
  }
  const headS = sd.sub(headF, sd.min(sd.ball(EYES[0].c, EYE_R * 1.15), sd.ball(EYES[1].c, EYE_R * 1.15)), 0.004);
  /* cupped, upright ears, set wide on top of the skull and leaning a little outward */
  const ear = (s) => {
    const F = sd.frame(EP(s), EROT(s));
    const outer = sd.xf(sd.limb([0, 0, 0], [0, 0.142, 0], 0.05, 0.016), [0, 0, 0], null, [1, 1, 0.42]);      /* a rounded tip, wider than one mesh cell, so no spike forms there */
    const cup = sd.xf(sd.limb([0, 0.012, 0], [0, 0.138, 0], 0.04, 0.008), [0, 0, 0.02], null, [1, 1, 0.36]);
    const m = new THREE.Matrix4().makeRotationFromEuler(new THREE.Euler(...EROT(s))).elements;
    return { F, f: F.place(sd.sub(outer, cup, 0.005)), up: [m[4], m[5], m[6]] };
  };
  const EAR = { L: ear(1), R: ear(-1) };
  const tailSeg = [];
  for (let i = 0; i < 6; i++) tailSeg.push(sd.limb(T[i], T[i + 1], TR[i], TR[i + 1]));
  const tailF = sd.add(0.02, ...tailSeg);
  const noseS = sd.xf(sd.egg([0, 0, 0], [0.018, 0.012, 0.011]), [0, 0.752, 0.232], [-0.45, 0, 0]);

  const trunk = sd.add(0.08, pelvis, thorax, sternum);
  const hind = sd.add(0.03, sd.add(0.06, trunk, thigh(1), thigh(-1), shank(1), shank(-1)), hfoot(1), hfoot(-1));
  const foreQ = sd.add(0.016, sd.add(0.03, hind, shoulder(1), shoulder(-1), neckF, arm(1), arm(-1)), fore(1), fore(-1), paw(1), paw(-1));      /* the forelegs stay two columns under the chest, with the notch between them */
  const withHead = sd.add(0.014, sd.add(0.045, foreQ, headS), EAR.L.f, EAR.R.f);
  const bodyAll = sd.add(0.03, withHead, tailF);
  const all = sd.min(bodyAll, noseS, sd.ball(EYES[0].c, EYE_R), sd.ball(EYES[1].c, EYE_R));

  /* ---------- which part a point belongs to (for the skin weights and the paint) ---------- */
  /* the upper arm lies inside the chest's outline on a sitting cat, so for the skin it claims the chest's skin over it, and the
     shoulder blade with it (the scapula rides with the arm): a lifted paw then brings a solid elbow forward out of the chest fur,
     not a flap of stretched skin */
  const armPart = (s) => sd.min(sd.limb(SJ(s), ELB(s), 0.1, 0.072), shoulder(s));
  const PARTS = {
    body: pelvis, chest: sd.min(thorax, sternum), neck: neckF, head: headS, earL: EAR.L.f, earR: EAR.R.f,
    armL: armPart(1), foreL: fore(1), pawL: paw(1), armR: armPart(-1), foreR: fore(-1), pawR: paw(-1),
    thighL: thigh(1), shankL: shank(1), hfootL: hfoot(1), thighR: thigh(-1), shankR: shank(-1), hfootR: hfoot(-1),
    tail1: tailSeg[0], tail2: tailSeg[1], tail3: tailSeg[2], tail4: tailSeg[3], tail5: tailSeg[4], tail6: tailSeg[5],
  };
  const PNAMES = Object.keys(PARTS), PFN = PNAMES.map((k) => PARTS[k]);
  const memo = { x: NaN, y: NaN, z: NaN, d: new Float64Array(PFN.length), min: 0 };
  function partsAt(x, y, z) {
    if (x === memo.x && y === memo.y && z === memo.z) return memo;
    memo.x = x; memo.y = y; memo.z = z;
    let mn = Infinity;
    for (let i = 0; i < PFN.length; i++) { const d = PFN[i](x, y, z); memo.d[i] = d; if (d < mn) mn = d; }
    memo.min = mn;
    return memo;
  }
  /* a bone owns the points on its own part's surface and fades out over 12 mm into the next part (8 mm for the forelegs,
     which swing far: a wider fade would pull a web of chest skin along with a lifted paw) */
  const member = (name, fade = 0.012) => { const i = PNAMES.indexOf(name); return (x, y, z) => { const m = partsAt(x, y, z); return Math.exp(-Math.max(0, m.d[i] - m.min) / fade); }; };

  /* ---------- the whiskers: twelve a side in four rows (the top row shortest), three over each eye ---------- */
  const WHISK = [];
  for (const s of [1, -1]) {
    const P0 = PADC(s);
    for (let row = 0; row < 4; row++) for (let col = 0; col < 3; col++) {
      const a = s * (0.5 + 0.34 * col), e = (1.5 - row) * 0.3;
      const root = [P0[0] + Math.sin(a) * Math.cos(e) * 0.03, P0[1] + Math.sin(e) * 0.026, P0[2] + Math.cos(a) * Math.cos(e) * 0.026];
      const dir = unit([s * (0.72 + 0.12 * col), (1.5 - row) * 0.24 - 0.1, 0.6 - 0.14 * col]);
      WHISK.push({ s, root, dir, len: 0.18 + 0.022 * row + 0.03 * col, brow: false });
    }
    for (let i = 0; i < 3; i++) {
      WHISK.push({ s, root: [s * (0.042 + 0.012 * i), 0.84, 0.15 - 0.012 * i], dir: unit([s * 0.5, 0.78, 0.3 - 0.1 * i]), len: 0.1 + 0.02 * i, brow: true });
    }
  }

  /* ---------- the coat ---------- */
  const MPTS = [[-0.086, 0.045], [-0.048, 0.126], [0, 0.072], [0.048, 0.126], [0.086, 0.045]];
  function facePaint(x, y, z, nx, ny, nz, c, n) {
    const hx = x - HC[0], hy = y - HC[1], hz = z - HC[2], ax = Math.abs(hx);
    const dark = mixc(DARK, DARK2, n);
    let d = 0, pale = 0;
    if (hy > 0.045 && hz < 0.095) {      /* thin stripes running back over the crown between the ears */
      let best = 1;
      for (let k = -2; k <= 2; k++) best = Math.min(best, Math.abs(hx - k * 0.03 - 0.004 * Math.sin(hz * 40 + k)));
      d = Math.max(d, band(best, 0.0058) * sst(0.1, 0.07, ax) * sst(0.3, 0.5, noise(x * 30, y * 30, z * 30 + 2)));
    }
    if (hz > 0.02 && hy > 0.035 && hy < 0.16) d = Math.max(d, band(poly2(hx, hy, MPTS), 0.0105, 0.004));      /* the M: a little bolder than life, so it survives the mesh's vertex spacing */
    for (const E of EYES) {
      const e = E.c, s = E.s, de = Math.hypot(x - e[0], y - e[1], z - e[2]) - EYE_R;
      d = Math.max(d, sst(0.017, 0.011, de) * sst(-0.004, 0.003, de));      /* the dark rim round the eye */
      pale = Math.max(pale, sst(0.011, 0.017, de) * sst(0.036, 0.026, de));      /* the pale spectacle */
      d = Math.max(d, band(seg3(x, y, z, add3(e, [s * 0.03, 0.004, -0.014]), add3(e, [s * 0.088, 0.036, -0.058])), 0.007));      /* the liner stroke toward the ear */
      d = Math.max(d, 0.8 * band(seg3(x, y, z, add3(e, [-s * 0.025, -0.016, 0.026]), add3(e, [-s * 0.03, -0.046, 0.042])), 0.0052));      /* the tear line */
      const cs = [[[s * 0.056, -0.02, 0.1], [s * 0.1, -0.04, 0.045], [s * 0.118, -0.064, -0.005]], [[s * 0.05, -0.048, 0.095], [s * 0.095, -0.072, 0.035]]];
      for (const pl of cs) for (let i = 0; i < pl.length - 1; i++) d = Math.max(d, 0.9 * band(seg3(hx, hy, hz, pl[i], pl[i + 1]), 0.0085, 0.004));      /* cheek stripes */
    }
    /* the mouth: the groove under the nose and the lip line curving back under the whisker pads */
    d = Math.max(d, band(seg3(hx, hy, hz, [0, -0.034, 0.147], [0, -0.052, 0.14]), 0.0032));
    for (const s of [1, -1]) {
      d = Math.max(d, 0.85 * band(seg3(hx, hy, hz, [0, -0.052, 0.14], [s * 0.028, -0.05, 0.132]), 0.003));
      d = Math.max(d, 0.7 * band(seg3(hx, hy, hz, [s * 0.028, -0.05, 0.132], [s * 0.05, -0.058, 0.108]), 0.003));
    }
    c = mixc(c, mixc(BASE2, BASE, 0.5), 0.5 * sst(0.03, 0.012, ax) * sst(-0.035, -0.01, hy) * sst(0.08, 0.11, hz));      /* the warm nose bridge */
    let pl = 0.7 * pale;
    pl = Math.max(pl, 0.9 * sst(0.075, 0.1, hz) * sst(-0.004, -0.024, hy));      /* the muzzle */
    pl = Math.max(pl, 0.9 * sst(-0.04, -0.06, hy) * sst(-0.01, 0.05, hz));      /* the chin */
    pl = Math.max(pl, 0.8 * sst(-0.07, -0.1, hy) * sst(1.1, 0.4, Math.abs(Math.atan2(hx, hz + 0.05))));      /* the throat */
    c = mixc(c, mixc(PALE, PALE2, 0.3 * n), pl);
    for (const W of WHISK) if (!W.brow && Math.hypot(x - W.root[0], y - W.root[1], z - W.root[2]) < 0.0055) d = Math.max(d, 0.75);      /* whisker spots */
    return mixc(c, dark, 0.9 * d);
  }
  function earPaint(E, s, x, y, z, c, n) {
    const l = E.F.loc(x, y, z), u = clamp(l[1] / 0.142, 0, 1), halfW = 0.05 * (1 - u) + 0.014, w = Math.abs(l[0]) / halfW;
    if (l[2] > 0.003 && w < 0.82) {      /* inside the cup: pale skin, whiter furnishings toward the front edge */
      return mixc(mixc(INNER, INNER2, 0.5 * n), PALE, 0.55 * sst(0.45, 0.85, w) + 0.3 * sst(0.3, 0.0, u));
    }
    const rim = sst(0.74, 0.92, w), tip = 0.7 * sst(0.8, 0.98, u), edge = Math.max(rim, tip);
    const thumb = sst(1, 0.72, Math.hypot(l[0] / 0.021, (l[1] - 0.075) / 0.034));      /* the pale thumbprint on the back */
    let cc = mixc(c, mixc(DARK, DARK2, n), 0.78 * edge);
    return mixc(cc, PALE2, 0.65 * thumb * (1 - edge));
  }
  function tailPaint(x, y, z, ny, c, n) {
    let best = Infinity, u = 0;
    for (let i = 0; i < 6; i++) {
      const t = clamp(along(T[i], T[i + 1], x, y, z), 0, 1), q = add3(T[i], mul3(add3(T[i + 1], mul3(T[i], -1)), t));
      const d = Math.hypot(x - q[0], y - q[1], z - q[2]);
      if (d < best) { best = d; u = i + t; }
    }
    const rings = sst(0.52, 0.78, 0.5 + 0.5 * Math.sin(u * TAU * 1.5 + 1.2 + 0.9 * noise(x * 20, y * 20, z * 20)));
    const tip = sst(5.35, 5.8, u), under = sst(-0.25, -0.7, ny);
    let cc = mixc(c, mixc(DARK, DARK2, n), 0.85 * Math.max(rings * (1 - 0.7 * under), tip));
    return mixc(cc, PALE2, 0.45 * under * (1 - tip) * (1 - rings));
  }
  function coat(x, y, z, nx, ny, nz) {
    const n = fbm(x * 28, y * 28, z * 28, 3), tick = fbm(x * 150, y * 150, z * 150, 2);
    let c = mixc(BASE, BASE2, 0.3 + 0.5 * n);
    c = mixc(c, TICK, 0.35 * sst(0.5, 0.82, tick));      /* agouti ticking */
    const ax = Math.abs(x), dark = mixc(DARK, DARK2, n);
    if (y < 0.26 && tailF(x, y, z) < Math.min(0.012, pelvis(x, y, z) - 0.002, hfoot(1)(x, y, z) - 0.002)) return tailPaint(x, y, z, ny, c, n);
    if (y > 0.8) { if (EAR.L.f(x, y, z) < 0.01) return earPaint(EAR.L, 1, x, y, z, c, n); if (EAR.R.f(x, y, z) < 0.01) return earPaint(EAR.R, -1, x, y, z, c, n); }
    if (y > 0.66 && headS(x, y, z) < neckF(x, y, z) + 0.01) return facePaint(x, y, z, nx, ny, nz, c, n);
    const phi = Math.atan2(ax, z + 0.05);      /* 0 at the front, PI at the spine */
    const legD = Math.min(arm(1)(x, y, z), arm(-1)(x, y, z), fore(1)(x, y, z), fore(-1)(x, y, z), paw(1)(x, y, z), paw(-1)(x, y, z));
    const trunkD = Math.min(trunk(x, y, z), neckF(x, y, z));
    const breaks = sst(0.28, 0.5, noise(x * 22, y * 22 + 5, z * 22));
    if (legD < trunkD - 0.004 && y < 0.52) {      /* a foreleg: rings on the outside, pale inside, pale toes */
      const s = x > 0 ? 1 : -1, ring = sst(0.62, 0.82, 0.5 + 0.5 * Math.sin(y * 64 + 1.5 * noise(x * 15, y * 15, z * 15)));
      const outer = sst(-0.3, 0.3, nx * s), inner = sst(0.1, -0.5, nx * s);
      c = mixc(c, mixc(PALE, PALE2, 0.4), 0.35 * inner * sst(0.4, 0.2, y) + 0.7 * sst(0.075, 0.03, y));
      return mixc(c, dark, 0.8 * ring * outer * sst(0.1, 0.16, y) * sst(0.5, 0.42, y) * breaks);
    }
    const lowHind = Math.min(shank(1)(x, y, z), shank(-1)(x, y, z), hfoot(1)(x, y, z), hfoot(-1)(x, y, z));
    if (lowHind < trunkD - 0.004 && y < 0.14) {      /* the hind feet and hocks */
      const ring = sst(0.62, 0.82, 0.5 + 0.5 * Math.sin(z * 50 + y * 30));
      c = mixc(c, mixc(PALE, PALE2, 0.4), 0.7 * sst(0.07, 0.03, y) + 0.3 * sst(0.1, 0.3, nz));
      return mixc(c, dark, 0.7 * ring * sst(0.05, 0.1, y) * breaks);
    }
    /* the trunk: mackerel bars radiating down the sides, a dark line down the spine, a pale bib and belly */
    const s = Math.atan2(y - 0.15, -(z - 0.2));
    const bars = 0.5 + 0.5 * Math.sin(s * 54 + 2.2 * noise(x * 14 + 3, y * 14, z * 14) + ax * 3);
    const flank = sst(0.7, 1.25, phi) * sst(2.8, 2.5, phi) * sst(0.02, 0.1, y);
    let d = sst(0.68, 0.84, bars) * flank * breaks;
    if (y > 0.5) d = Math.max(d, sst(0.65, 0.82, 0.5 + 0.5 * Math.sin(y * 62 + 1.6 * noise(x * 15, y * 15, z * 15))) * sst(0.9, 1.4, phi) * breaks);      /* rings round the nape */
    d = Math.max(d, 0.85 * sst(0.03, 0.012, ax) * sst(2.3, 2.7, phi) * sst(0.1, 0.18, y));      /* the dorsal line */
    const front = sst(0.95, 0.4, phi) * sst(0.64, 0.56, y);
    c = mixc(c, mixc(PALE, PALE2, 0.3 + 0.5 * n), 0.8 * front * (1 - d));
    const necklace = front * sst(0.6, 0.82, 0.5 + 0.5 * Math.sin(y * 72 + 2 * noise(x * 9, y * 9, z * 9))) * sst(0.34, 0.4, y) * sst(0.56, 0.5, y) * breaks;
    c = mixc(c, DARK2, 0.5 * necklace);
    return mixc(c, dark, 0.86 * d);
  }
  /* the groom: short on the face and legs, a ruff round the neck and chest, long on the tail; combed back and down;
     none across the eyes, the nose or inside the ears */
  function groom(x, y, z, nx, ny, nz) {
    let len = 0.95, dens = 1, cx = 0, cy = -0.55, cz = -1;
    if (y < 0.26 && tailF(x, y, z) < Math.min(0.012, pelvis(x, y, z) - 0.002)) {
      let best = Infinity, dir = [0, 0, 1], u = 0;
      for (let i = 0; i < 6; i++) { const d = seg3(x, y, z, T[i], T[i + 1]); if (d < best) { best = d; dir = unit(add3(T[i + 1], mul3(T[i], -1))); u = i + clamp(along(T[i], T[i + 1], x, y, z), 0, 1); } }
      return [lerp(1.1, 0.8, sst(4.5, 6, u)), 1, dir[0] * 0.8, dir[1] * 0.8 - 0.3, dir[2] * 0.8];
    }
    if (y > 0.8) for (const E of [EAR.L, EAR.R]) if (E.f(x, y, z) < 0.01) {
      const l = E.F.loc(x, y, z), u = clamp(l[1] / 0.142, 0, 1), halfW = 0.05 * (1 - u) + 0.014, w = Math.abs(l[0]) / halfW;
      if (l[2] > 0.003 && w < 0.82) return [0.16 + 0.5 * sst(0.5, 0.85, w) * (1 - u), 0.4, E.up[0], E.up[1], E.up[2]];
      return [0.45 * (1 - 0.8 * u * u), 1, E.up[0], E.up[1], E.up[2]];      /* short at the tip: no stray bristle standing off the point */
    }
    if (y > 0.66 && headS(x, y, z) < neckF(x, y, z) + 0.01) {
      const hx = x - HC[0], hy = y - HC[1], hz = z - HC[2], sx = hx < 0 ? -1 : 1;
      len = 0.5 * lerp(1, 0.55, sst(0.08, 0.14, hz));
      len *= lerp(1, 1.45, sst(0.045, 0.09, Math.abs(hx)) * sst(0.02, -0.03, hy));      /* the cheek ruff */
      for (const E of EYES) len *= sst(0.0, 0.02, Math.hypot(x - E.c[0], y - E.c[1], z - E.c[2]) - EYE_R * 1.28);
      len *= sst(0.0, 0.03, Math.hypot(x, y - 0.752, z - 0.232) - 0.014);
      const onCrown = sst(0.03, 0.08, hy);
      cx = sx * 0.45 * (1 - onCrown); cy = -0.5 * (1 - onCrown) + 0.15 * onCrown; cz = -0.75;
      return [len, 1, cx, cy, cz];
    }
    const legD = Math.min(arm(1)(x, y, z), arm(-1)(x, y, z), fore(1)(x, y, z), fore(-1)(x, y, z), paw(1)(x, y, z), paw(-1)(x, y, z));
    const trunkD = Math.min(trunk(x, y, z), neckF(x, y, z));
    if (legD < trunkD - 0.004 && y < 0.52) return [lerp(0.55, 0.38, sst(0.12, 0.05, y)), 1, 0, -1, 0.1];
    const lowHind = Math.min(shank(1)(x, y, z), shank(-1)(x, y, z), hfoot(1)(x, y, z), hfoot(-1)(x, y, z));
    if (lowHind < trunkD - 0.004 && y < 0.14) return [0.45, 1, 0, -0.5, 1];
    const phi = Math.atan2(Math.abs(x), z + 0.05);
    len = 0.95 + 0.3 * sst(0.9, 0.4, phi) * sst(0.4, 0.5, y) * sst(0.68, 0.6, y);      /* the ruff and bib */
    len += 0.1 * sst(0.35, 0.2, y);      /* the haunches */
    return [len, dens, cx, cy, cz];
  }

  /* ---------- materials ---------- */
  const furM = K.physical({ rough: 0.78, sheen: 0.45, sheenRough: 0.6, sheenColor: 0xd8c8a8, spec: 0.25, name: 'cat-fur' });
  const noseM = K.physical({ rough: 0.48, clearcoat: 0.4, ccRough: 0.25, spec: 0.5, name: 'cat-nose' });
  const pupilM = K.physical({ color: 0x050403, vertexColors: false, rough: 0.35, spec: 0.25, env: 0.25, name: 'cat-pupil' });
  pupilM.polygonOffset = true; pupilM.polygonOffsetFactor = -1; pupilM.polygonOffsetUnits = -2;
  const whiskM = new THREE.LineBasicMaterial({ color: 0xf4f1ea, transparent: true, opacity: 0.6, depthWrite: false });

  /* ---------- joints (bones): the spine, the folded hind legs, the forelegs, the tail chain, the ears, the whiskers ---------- */
  K.joint(R, 'body', 'pose', [0, 0.25, -0.17]);
  K.joint(R, 'chest', 'body', CP);
  K.joint(R, 'neck', 'chest', NP0);
  K.joint(R, 'head', 'neck', NP1);
  K.joint(R, 'earL', 'head', EP(1)); K.joint(R, 'earR', 'head', EP(-1));
  for (const s of [1, -1]) {
    const L = s > 0 ? 'L' : 'R';
    K.joint(R, 'arm' + L, 'chest', SJ(s)); K.joint(R, 'fore' + L, 'arm' + L, ELB(s)); K.joint(R, 'paw' + L, 'fore' + L, WR(s));
    K.joint(R, 'thigh' + L, 'body', HIP(s)); K.joint(R, 'shank' + L, 'thigh' + L, STIF(s)); K.joint(R, 'hfoot' + L, 'shank' + L, HOCK(s));
    K.joint(R, 'whk' + L, 'head', [s * 0.03, 0.727, 0.2]);
  }
  for (let i = 0; i < 6; i++) K.joint(R, 'tail' + (i + 1), i ? 'tail' + i : 'body', T[i]);
  K.limit(R, 'head', { ry: [-1.15, 1.15], rx: [-0.55, 0.65], rz: [-0.5, 0.5] });
  K.limit(R, 'neck', { ry: [-0.5, 0.5], rx: [-0.4, 0.4] });
  for (const e of ['earL', 'earR']) K.limit(R, e, { rx: [-0.5, 0.9], ry: [-1.2, 1.2], rz: [-0.6, 0.6] });

  /* ---------- secondary motion: the tail follows every move through and swings against the body's own acceleration (it is
     the cat's counterweight, Walker 1998), the tip fastest; the ears and whiskers lag a quick head turn by a frame or two ---------- */
  const TDIR = (i) => unit(add3(T[i + 1], mul3(T[i], -1)));
  K.spring(R, 'tail3', { ch: 'ry', k: 90, c: 8, gain: 0.03, dir: TDIR(2), lim: [-0.35, 0.35] });
  K.spring(R, 'tail4', { ch: 'ry', k: 120, c: 9, gain: 0.04, dir: TDIR(3), lim: [-0.4, 0.4] });
  K.spring(R, 'tail5', { ch: 'ry', k: 160, c: 10, gain: 0.05, dir: TDIR(4), lim: [-0.5, 0.5] });
  K.spring(R, 'tail6', { ch: 'ry', k: 230, c: 12, gain: 0.06, dir: TDIR(5), lim: [-0.6, 0.6] });
  K.spring(R, 'tail6', { ch: 'rx', k: 210, c: 12, gain: 0.04, dir: TDIR(5), lim: [-0.4, 0.4] });
  for (const s of [1, -1]) {
    const L = s > 0 ? 'L' : 'R';
    K.spring(R, 'ear' + L, { ch: 'rz', k: 320, c: 18, gain: 0.006, dir: (s > 0 ? EAR.L : EAR.R).up, lim: [-0.12, 0.12] });
    K.spring(R, 'whk' + L, { ch: 'ry', k: 420, c: 22, gain: 0.004, dir: [s * 0.8, 0, 0.6], lim: [-0.1, 0.1] });
  }

  /* ---------- the skinned body with its fur ---------- */
  const EARUP = (s) => { const E = s > 0 ? EAR.L : EAR.R; return add3(EP(s), mul3(E.up, 0.15)); };
  const BONES = [
    { j: 'body', a: [0, 0.1, -0.2], b: [0, 0.33, -0.15], r: 0.26, only: member('body') },
    { j: 'chest', a: [0, 0.33, -0.06], b: [0, 0.58, 0.02], r: 0.24, only: member('chest') },
    { j: 'neck', a: NP0, b: NP1, r: 0.14, only: member('neck') },
    { j: 'head', a: [0, 0.7, 0.06], b: [0, 0.86, 0.11], r: 0.22, only: member('head') },
    { j: 'earL', a: EP(1), b: EARUP(1), r: 0.09, only: member('earL') },
    { j: 'earR', a: EP(-1), b: EARUP(-1), r: 0.09, only: member('earR') },
  ];
  for (const s of [1, -1]) {
    const L = s > 0 ? 'L' : 'R';
    BONES.push({ j: 'arm' + L, a: SJ(s), b: ELB(s), r: 0.09, only: member('arm' + L, 0.008) }, { j: 'fore' + L, a: ELB(s), b: WR(s), r: 0.08, only: member('fore' + L, 0.008) },
      { j: 'paw' + L, a: WR(s), b: FTOE(s), r: 0.08, only: member('paw' + L, 0.008) },
      { j: 'thigh' + L, a: HIP(s), b: STIF(s), r: 0.14, only: member('thigh' + L) }, { j: 'shank' + L, a: STIF(s), b: HOCK(s), r: 0.1, only: member('shank' + L) },
      { j: 'hfoot' + L, a: HOCK(s), b: [s * 0.165, 0.025, 0.12], r: 0.09, only: member('hfoot' + L) });
  }
  for (let i = 0; i < 6; i++) BONES.push({ j: 'tail' + (i + 1), a: T[i], b: T[i + 1], r: 0.08, only: member('tail' + (i + 1)) });
  const bodyGeo = surf(bodyAll, [-0.38, -0.012, -0.47, 0.38, 1.03, 0.33], 0.0092, coat, { ao: all, groom });
  const bodyMesh = K.skin(R, bodyGeo, BONES, furM, { smooth: 3, name: 'cat-body' });
  K.fur(R, bodyMesh, { len: 0.024, dens: 150, thin: 0.85, root: 0.72, clump: 0.45, comb: 0.65, droop: 0.2, min: 0.4 });

  /* ---------- the nose leather, on the head ---------- */
  K.put(R, 'head', surf(noseS, [-0.026, 0.735, 0.215, 0.026, 0.77, 0.25], 0.0032, (x, y, z) => mixc(NOSE, NOSE2, 0.5 * sst(0.005, 0.013, Math.abs(x)) + 0.4 * sst(0.748, 0.742, y)), { ao: all }), noseM);

  /* ---------- the eyes: amber, wet, with a vertical slit pupil; the iris turns inside the lids ---------- */
  const irisTex = K.tex.canvas(128, 64, (g, W, H) => {
    const img = g.createImageData(W, H), d = img.data, irisA = 1.08;      /* the iris fills the whole opening: no white shows in a cat's eye */
    const ic = rgb(0xc49b3c), ic2 = rgb(0x8c6a24), ring = rgb(0xdcb95e), limb = rgb(0x2a1c10), sc = rgb(0x6f5f4e);
    for (let y = 0; y < H; y++) {
      const th = ((y + 0.5) / H) * PI, r = th / irisA;
      for (let x = 0; x < W; x++) {
        const i = 4 * (x + y * W), u = x / W;
        let c;
        if (r >= 1.04) c = sc;
        else if (r >= 0.96) c = mixc(limb, sc, sst(0.96, 1.04, r));
        else {
          const fib = 0.5 + 0.5 * Math.sin(u * TAU * 40 + r * 11) * (0.6 + 0.4 * Math.sin(u * TAU * 9 + 2));
          let base = mixc(ic, ic2, 0.6 * fib * sst(0.2, 0.95, r));
          base = mixc(base, ring, 0.5 * sst(0.45, 0.2, r) * sst(0.05, 0.15, r));
          c = mixc(base, limb, sst(0.68, 1, r) * 0.75);
        }
        d[i] = Math.round(c[0] * 255); d[i + 1] = Math.round(c[1] * 255); d[i + 2] = Math.round(c[2] * 255); d[i + 3] = 255;
      }
    }
    g.putImageData(img, 0, 0);
  });
  /* the pupil: a lens on the eye's surface, narrow at rest, scaled wider by the clips (built at rest width) */
  function pupilGeo(r) {
    const w = 0.17, h = 0.52, nb = 14, na = 6, P = [], idx = [];      /* a slit about a third of the iris's width in a lit room (Malmström & Kröger 2006); the clips widen it */
    for (let j = 0; j <= nb; j++) {
      const b = -h + (2 * h * j) / nb, aw = w * (1 - (b / h) * (b / h)) + 1e-4;
      for (let i = 0; i <= na; i++) {
        const a = -aw + (2 * aw * i) / na, sx = Math.sin(a), sy = Math.sin(b), cz = Math.sqrt(Math.max(0, 1 - sx * sx - sy * sy));
        P.push(sx * r, sy * r, cz * r);
      }
    }
    for (let j = 0; j < nb; j++) for (let i = 0; i < na; i++) {
      const a = j * (na + 1) + i, b = a + 1, c = a + na + 2, dd = a + na + 1;
      idx.push(a, b, c, a, c, dd);
    }
    const g = new THREE.BufferGeometry();
    g.setAttribute('position', new THREE.Float32BufferAttribute(P, 3));
    g.setIndex(idx); g.computeVertexNormals();
    return g;
  }
  /* the lids: a thin dark rim (the liner every tabby wears) and then the fur of the face */
  const lidPaint = (lidR) => (x, y, z) => {
    const t = y / lidR, fur = mixc(mixc(DARK2, DARK, 0.5), BASE2, 0.3 * fbm(x * 90 + 7, y * 90, z * 90, 2));      /* the dark lid margin every tabby wears, mottled, never a smooth bead */
    return t < 0.05 ? LINER : mixc(LINER, fur, sst(0.05, 0.22, t));
  };
  for (const E of EYES) {
    const L = E.s > 0 ? 'L' : 'R', name = 'eye' + L, lidR = EYE_R * 1.1;
    const j = K.eye(R, name, 'head', E.c, E.dl, EYE_R, {
      map: irisTex, irisAngle: 1.08, lid: lidPaint(lidR), lidLo: lidPaint(lidR), lidMat: { rough: 0.9, sheen: 0.2, sheenRough: 0.8, spec: 0.15, env: 0.35, name: name + '-lid' },
      open: -0.62, shut: 1.0, glint: 0.26, glintA: 0.85, lowerShare: 0.35, gloss: 0.8, wet: 0.5, corneaAngle: 1.0,
    });
    const gaze = K.local(R, 'gaze' + L, name, [0, 0, 0]);
    const ball = j.children.find((x) => x.name === name + '-mesh');
    if (ball) gaze.add(ball);
    K.limit(R, 'gaze' + L, { ry: [-0.45, 0.45], rx: [-0.3, 0.3] });
    const pj = K.local(R, 'pup' + L, 'gaze' + L, [0, 0, 0]);
    const pm = K.put(R, 'pup' + L, pupilGeo(EYE_R * 1.006), pupilM, true);
    pm.castShadow = false; pm.receiveShadow = false;
    void pj;
  }

  /* ---------- whiskers: fine lines from the pads and brows, on joints that swing them forward ---------- */
  for (const s of [1, -1]) {
    const L = s > 0 ? 'L' : 'R', piv = R.piv['whk' + L], v = [];
    for (const W of WHISK) {
      if (W.s !== s) continue;
      const p0 = W.root, p1 = add3(add3(W.root, mul3(W.dir, 0.5 * W.len)), [0, -0.004, 0]), p2 = add3(add3(W.root, mul3(W.dir, W.len)), W.brow ? [0, -0.006, -0.01] : [0, -0.03 * (W.len / 0.22), -0.012]);
      v.push(...p0, ...p1, ...p1, ...p2);
    }
    const g = new THREE.BufferGeometry();
    g.setAttribute('position', new THREE.Float32BufferAttribute(v, 3));
    g.translate(-piv[0], -piv[1], -piv[2]);
    const lines = new THREE.LineSegments(g, whiskM);
    lines.name = 'whiskers-' + L; lines.frustumCulled = false; lines.renderOrder = 5;
    R.j['whk' + L].add(lines); R.geos.push(g); R.mats.add(whiskM);
  }

  /* ---------- the tail-up: the turns that stand each segment up with the tip hooked forward (Cafazzo & Natoli 2009) ---------- */
  const TAIL_UP = (() => {
    const targets = [[0.08, 1, -0.12], [0.08, 1, -0.1], [0.06, 1, -0.05], [0.05, 1, 0.05], [0.1, 0.8, 0.55], [0.05, 0.25, 0.95]].map((t) => new THREE.Vector3(...t).normalize());
    const Q = new THREE.Quaternion(), out = [];
    for (let i = 0; i < 6; i++) {
      const seg = new THREE.Vector3(T[i + 1][0] - T[i][0], T[i + 1][1] - T[i][1], T[i + 1][2] - T[i][2]).normalize();
      const tl = targets[i].clone().applyQuaternion(Q.clone().invert());
      const q = new THREE.Quaternion().setFromUnitVectors(seg, tl);
      out.push(q); Q.multiply(q);
    }
    return out;
  })();
  const Q0 = new THREE.Quaternion(), QT = new THREE.Quaternion(), ET = new THREE.Euler();
  /* kOf(i) gives each segment its own share (a wave travelling up the tail); every share 0 gives the rest pose exactly */
  const tailUp = (o, kOf) => {
    for (let i = 0; i < 6; i++) {
      const k = clamp(kOf(i), 0, 1);
      if (k <= 0) continue;
      QT.copy(Q0).slerp(TAIL_UP[i], k); ET.setFromQuaternion(QT, 'XYZ');
      o('tail' + (i + 1), 'rx', ET.x); o('tail' + (i + 1), 'ry', ET.y); o('tail' + (i + 1), 'rz', ET.z);
    }
  };

  /* ---------- planted forepaws: the elbows fold as the chest comes down or forward (two-bone IK, Day & Jayne angles at rest) ---------- */
  const L1 = dist3(SJ(1), ELB(1)), L2 = dist3(ELB(1), WR(1));
  const REST_IK = K.ik2(L1, L2, WR(1)[2] - SJ(1)[2], WR(1)[1] - SJ(1)[1], -1);
  function plant(o, cRx, dy, dz, w = 1) {
    if (Math.abs(cRx) + Math.abs(dy) + Math.abs(dz) < 1e-9 || w <= 0) return;
    const cs = Math.cos(cRx), sn = Math.sin(cRx);
    for (const s of [1, -1]) {
      const S0 = SJ(s), ry = S0[1] - CP[1], rz = S0[2] - CP[2];
      const sy = CP[1] + ry * cs - rz * sn + dy, sz = CP[2] + ry * sn + rz * cs + dz;
      const Wr = WR(s), vy = Wr[1] - sy, vz = Wr[2] - sz;
      const ly = vy * cs + vz * sn, lz = -vy * sn + vz * cs;
      const ik = K.ik2(L1, L2, lz, ly, -1), dA = -(ik[0] - REST_IK[0]), dF = -(ik[1] - REST_IK[1]);
      const L = s > 0 ? 'L' : 'R';
      o('arm' + L, 'rx', dA * w); o('fore' + L, 'rx', dF * w); o('paw' + L, 'rx', -(cRx + dA + dF) * w);
    }
  }
  /* the crouch: the chest tips forward and down while the paws stay planted; the neck and head keep the eyes level */
  function crouch(o, a, w = 1) {
    if (a <= 0) return;
    const cRx = 0.34 * a, dy = -0.012 * a;
    o('chest', 'rx', cRx * w); o('body', 'py', dy * w);
    o('neck', 'rx', -0.5 * cRx * w); o('head', 'rx', -0.5 * cRx * w);
    plant(o, cRx, dy, 0, w);
  }

  /* ---------- the hair-trigger habits: ear flicks, half-blinks, the tail tip, idle fixations (deterministic from the clock) ---------- */
  const hsh = (i, k) => { let h = Math.imul(i | 0, 0x27d4eb2d) ^ Math.imul((k | 0) + 1, 0x165667b1); h = Math.imul(h ^ (h >>> 15), 0x2c1b3c6d); h ^= h >>> 12; return (h >>> 0) / 4294967296; };
  const ev = (t, period, k) => { const i = Math.floor(t / period); return { u: t - (i + 0.7 * hsh(i, k)) * period, i }; };
  const bump = (u, a, b) => { if (u <= a || u >= b) return 0; const s = Math.sin((PI * (u - a)) / (b - a)); return s * s; };
  R.spec.life = (o, L) => {
    const t = L.t, sigh = 1 + 0.6 * sst(0.8, 1, Math.sin(t * 0.09 + 1.1)), b = L.b * sigh;
    /* breathing: the ribs and the flank behind them, a slight lift of the shoulders and head (15 to 30 a minute) */
    o('chest', 'sx', 0.018 * b); o('chest', 'sz', 0.014 * b); o('chest', 'sy', 0.004 * b);
    o('body', 'sx', 0.008 * b); o('body', 'sz', 0.006 * b);
    o('neck', 'py', 0.0025 * b); o('head', 'rx', -0.006 * b);
    o('armL', 'rz', -0.008 * b); o('armR', 'rz', 0.008 * b);
    if (L.still) return;
    /* attention: the head turns (eyes reach only 25 degrees); the eyes lead into the gap and come back as the head arrives */
    const k = 1 - Math.min(1, R.ctl.look), gapY = R.look.ty * k - L.yaw, gapP = R.look.tp * k - L.pitch;
    o('head', 'ry', L.yaw); o('head', 'rx', 0.75 * L.pitch); o('head', 'rz', -0.08 * L.yaw);
    o('neck', 'ry', 0.25 * L.yaw); o('chest', 'ry', 0.08 * L.yaw);
    const att = clamp(Math.abs(L.yaw) / 0.3 + Math.abs(gapY) / 0.2 + Math.abs(L.pitch) / 0.25, 0, 1);
    /* idle fixations: the eyes settle on a new spot every few seconds and jump there in 80 ms */
    const fx = ev(t, 2.7, 6), prevY = (hsh(fx.i - 1, 7) - 0.5) * 0.26, nowY = (hsh(fx.i, 7) - 0.5) * 0.26, prevP = (hsh(fx.i - 1, 8) - 0.5) * 0.14, nowP = (hsh(fx.i, 8) - 0.5) * 0.14;
    const fw = sst(0, 0.08, fx.u), fixY = lerp(prevY, nowY, fw) * (1 - att), fixP = lerp(prevP, nowP, fw) * (1 - att);
    const ey = clamp(0.9 * gapY, -0.35, 0.35) + fixY, ep = clamp(0.9 * gapP, -0.25, 0.25) + fixP;
    o('gazeL', 'ry', ey); o('gazeR', 'ry', ey); o('gazeL', 'rx', ep); o('gazeR', 'rx', ep);
    /* the ears swivel toward the target before the head starts, and both come forward when it is engaged */
    const earTo = clamp(R.look.ty * k, -0.5, 0.5) * 0.4;
    o('earL', 'ry', earTo); o('earR', 'ry', earTo);
    o('earL', 'rx', -0.14 * att); o('earR', 'rx', -0.14 * att);
    o('whkL', 'ry', -0.28 * att); o('whkR', 'ry', 0.28 * att);
    o('pupL', 'sx', 0.7 * att); o('pupR', 'sx', 0.7 * att);
    /* one ear flicks back and returns, every 5 to 10 seconds */
    const fl = ev(t, 7.5, 1), f = sst(0, 0.1, fl.u) * (1 - sst(0.6, 0.85, fl.u));
    if (f > 0) { const e = hsh(fl.i, 2) < 0.5 ? 'earL' : 'earR', sg = e === 'earL' ? -1 : 1; o(e, 'ry', sg * 0.55 * f); o(e, 'rx', 0.25 * f); }
    /* a half-blink between the full blinks: one lid part way, never closed */
    const hb = ev(t, 8, 3);
    o('ctl', 'lid', 0.3 * sst(0, 0.15, hb.u) * (1 - sst(0.15, 0.45, hb.u)));
    /* the tail tip lifts and settles, or flicks once, every 3 to 8 seconds; a slow sway underneath */
    const tl = ev(t, 5.5, 4), flick = hsh(tl.i, 5) > 0.6;
    const tb = bump(tl.u, 0, 1.4);
    o('tail6', 'rx', -0.3 * tb * (flick ? 0.3 : 1)); o('tail5', 'rx', -0.12 * tb * (flick ? 0.3 : 1));
    if (flick) o('tail6', 'ry', 0.45 * Math.sin(TAU * 1.6 * tl.u) * bump(tl.u, 0, 0.7));
    o('tail6', 'ry', 0.05 * Math.sin(t * 0.7)); o('tail5', 'ry', 0.03 * Math.sin(t * 0.5 + 1));
    o('earL', 'ry', 0.03 * Math.sin(t * 0.37)); o('earR', 'ry', -0.03 * Math.sin(t * 0.31 + 2));
  };
  R.spec.duck = (o, d) => { o('mover', 'px', 0.32 * d); o('pose', 'ry', 0.42 * d); o('head', 'rx', 0.12 * d); o('earL', 'rx', 0.15 * d); o('earR', 'rx', 0.15 * d); };

  /* ---------- clips ---------- */
  const look = (o, e) => { if (e > 0) { o('head', 'ry', FACE * e); o('ctl', 'look', e); } };
  const ears = (o, rx, e) => { o('earL', 'rx', rx * e); o('earR', 'rx', rx * e); };
  const pupils = (o, e) => { o('pupL', 'sx', e); o('pupR', 'sx', e); };
  const whisk = (o, e) => { o('whkL', 'ry', -0.3 * e); o('whkR', 'ry', 0.3 * e); };
  R.clips = {
    arrive: { dur: 2.1, fn(p, o, c) { /* drops in from above in the gathered flight, lands forepaws first, the hind feet follow, settles into the sit; the tail flagged up through the jump sweeps round last */
      const u = Math.min(1, p / 0.21), fl = 1 - c.ramp(p, 0.17, 0.28);
      o('mover', 'py', 1.8 * (1 - u) * (1 - u));
      o('mover', 'px', 0.12 * (1 - c.ramp(p, 0, 0.3)));
      o('chest', 'rx', 0.3 * fl); o('head', 'rx', 0.35 * fl); o('neck', 'rx', 0.1 * fl);
      for (const L of ['L', 'R']) { o('fore' + L, 'rx', 0.5 * fl); o('paw' + L, 'rx', 0.7 * fl); o('thigh' + L, 'rx', -0.3 * fl); o('shank' + L, 'rx', 0.2 * fl); o('hfoot' + L, 'rx', 0.3 * fl); }
      const a = c.keys(p, [[0.2, 0], [0.3, 1], [0.42, 0.15], [0.52, 0]]);
      crouch(o, a);
      o('body', 'py', c.keys(p, [[0.2, 0], [0.29, -0.05], [0.4, 0.008], [0.5, 0], [0.8, 0], [0.9, -0.012], [1, 0]]));
      o('head', 'rx', c.keys(p, [[0.26, 0], [0.42, -0.08], [0.55, 0], [1, 0]]));
      look(o, c.keys(p, [[0.28, 0], [0.5, 1], [0.8, 1], [1, 0]]));
      ears(o, -0.22, c.keys(p, [[0, 1], [0.5, 1], [0.8, 0], [1, 0]]));
      pupils(o, 1.3 * fl);
      tailUp(o, (i) => c.keys(p - i * 0.012, [[0, 1], [0.45, 1], [0.52, 0.85], [0.9, 0]]));
      o('tail6', 'ry', 0.2 * Math.sin(c.TAU * 2.5 * p) * fl);
    } },
    idleA: { dur: 5, fn(p, o, c) { /* a deeper breath, one ear flick, a half-blink, the tail tip curling, the eyes drifting */
      o('ctl', 'amp', 0.8 * c.bump(p, 0.15, 0.7));
      const f = sst(0.2, 0.22, p) * (1 - sst(0.3, 0.35, p));
      o('earR', 'ry', -0.5 * f); o('earR', 'rx', 0.2 * f);
      o('ctl', 'lid', 0.3 * c.bump(p, 0.5, 0.6));
      o('tail6', 'rx', -0.3 * c.bump(p, 0.3, 0.8)); o('tail6', 'ry', 0.15 * Math.sin(c.TAU * p) * c.env(p, 0.2, 0.3));
      const e = c.env(p, 0.2, 0.3);
      o('gazeL', 'ry', 0.12 * Math.sin(c.TAU * p) * e); o('gazeR', 'ry', 0.12 * Math.sin(c.TAU * p) * e);
      o('head', 'rz', 0.03 * Math.sin(c.TAU * p) * e);
    } },
    idleB: { variants: 4, dur: (v) => [1.6, 2.4, 3.9, 3.6][v], fn(p, o, c) {
      if (c.v === 0) { /* a flick of the tail tip */
        const f = c.bump(p, 0.1, 0.32) - 0.8 * c.bump(p, 0.32, 0.55) + 0.4 * c.bump(p, 0.55, 0.75);
        o('tail6', 'ry', 0.7 * f); o('tail5', 'ry', 0.3 * f); o('tail6', 'rz', 0.2 * f);
      } else if (c.v === 1) { /* the ears swivel, one and then the other */
        const a = c.keys(p, [[0, 0], [0.08, 1], [0.45, 1], [0.58, 0], [1, 0]]), b = c.keys(p, [[0.35, 0], [0.42, 1], [0.85, 1], [0.97, 0], [1, 0]]);
        o('earL', 'ry', -0.6 * a); o('earL', 'rx', 0.15 * a); o('earR', 'ry', 0.6 * b); o('earR', 'rx', 0.15 * b);
        o('head', 'rz', 0.03 * (a - b));
      } else if (c.v === 2) { /* the face wash (half of all grooming goes to the face, Kim 2018): the elbow folds to bring a forepaw up
                                 while the head comes down to it, licks at the wrist with the head nodding, then two sweeps of the paw
                                 up past the eye and ear with the head rolled down to meet it, the eye on that side closing */
        const s = c.r < 0.5 ? 1 : -1, L = s > 0 ? 'L' : 'R';
        const lift = c.keys(p, [[0, 0], [0.08, 1], [0.86, 1], [0.97, 0], [1, 0]]);
        const up = c.keys(p, [[0.42, 0], [0.5, 1], [0.6, 0], [0.64, 0], [0.72, 1], [0.82, 0], [1, 0]]);
        /* the elbow comes forward just clear of the chest and the forearm folds up in front of it: the wrist at chin height for the
           licks, the paw's back up past the eye for the sweeps (the sculpt's elbow sits under the chest, so a fold alone would
           hide the paw inside the body) */
        o('arm' + L, 'rx', (-0.5 - 0.12 * up) * lift); o('fore' + L, 'rx', (-1.4 - 0.2 * up) * lift); o('paw' + L, 'rx', (1.2 + 0.3 * up) * lift);
        o('arm' + L, 'rz', -s * 0.16 * lift);
        crouch(o, 0.4 * lift);      /* the chest leans forward over the paw */
        const licks = c.bump(p, 0.08, 0.42) + c.bump(p, 0.78, 0.88);
        o('head', 'rx', 0.58 * lift + 0.07 * Math.sin(c.TAU * 2.4 * p * 3.9) * licks);      /* the head comes down to the paw and nods with each lick, about two a second */
        o('neck', 'rx', 0.38 * lift);
        o('head', 'ry', s * (0.4 * (1 - up) + 0.45 * up) * lift); o('head', 'rz', s * 0.1 * (1 - up) * lift - s * 0.5 * up);
        o('ear' + L, 'rx', 0.7 * up); o('ear' + L, 'rz', -s * 0.3 * up);
        o('eye' + L + 'Lid', 'rx', 2.0 * up);
        o('ctl', 'lid', 0.25 * lift * (1 - up));
        o('ctl', 'look', lift);
        o('body', 'rz', -s * 0.03 * lift);
      } else { /* settling: lower, rounder, eyes narrowing, then up again */
        const e = c.keys(p, [[0, 0], [0.3, 1], [0.75, 1], [1, 0]]);
        crouch(o, 0.45 * e);
        o('body', 'py', -0.012 * e); o('chest', 'rx', 0.05 * e);
        o('head', 'rx', 0.1 * e); o('head', 'py', -0.01 * e);
        o('earL', 'rz', -0.12 * e); o('earR', 'rz', 0.12 * e);
        o('ctl', 'lid', 0.4 * e);
        o('tail6', 'ry', 0.2 * e);
      }
    } },
    notice: { dur: 1.3, fn(p, o, c) { /* ears first, then the head turns to the person in 0.3 s with a small overshoot and comes level and forward */
      const e = c.keys(p, [[0, 0], [0.02, 0], [0.25, 1.07], [0.33, 1], [0.72, 1], [1, 0]]);
      ears(o, -0.24, c.keys(p, [[0, 0], [0.04, 1], [0.7, 1], [1, 0]]));
      look(o, e);
      o('head', 'rx', -0.06 * e); o('neck', 'pz', 0.015 * e); o('neck', 'rx', -0.04 * e);
      pupils(o, 0.7 * e); whisk(o, e);
    } },
    react: { dur: 1.9, fn(p, o, c) { /* the slow blink, the cat's greeting: two half-blinks, then the lids close slowly, hold, and open (Humphrey 2020) */
      const f = c.keys(p, [[0, 0], [0.12, 1], [0.88, 1], [1, 0]]);
      look(o, f);
      const closed = c.keys(p, [[0.4, 0], [0.58, 0.82], [0.79, 0.82], [1, 0]]);
      o('ctl', 'lid', Math.max(0.3 * c.bump(p, 0.08, 0.21), 0.3 * c.bump(p, 0.24, 0.37), closed));
      o('head', 'rx', 0.08 * closed / 0.82);
      ears(o, 0.25, closed / 0.82);
      o('tail6', 'ry', 0.15 * Math.sin(c.TAU * p) * c.env(p, 0.2, 0.3));
    } },
    talk: { dur: 3, fn(p, o, c) { /* attentive: ears forward, small nods at about one a second, a half-blink, the tail tip swaying */
      const e = c.env(p, 0.12, 0.2);
      look(o, 0.85 * e);
      o('head', 'rx', (0.05 * Math.sin(c.TAU * 3 * p) - 0.03) * e); o('head', 'rz', 0.05 * Math.sin(c.TAU * p) * e);
      ears(o, -0.16, e); pupils(o, 0.4 * e); whisk(o, 0.6 * e);
      o('tail6', 'ry', 0.25 * Math.sin(c.TAU * 1.5 * p) * e);
      o('ctl', 'lid', 0.3 * c.bump(p, 0.58, 0.7));
    } },
    lookLeft: { dur: 1.2, fn(p, o, c) { /* a saccade-like turn: the eyes lead, the head follows with a touch of overshoot, the eyes come back */
      const e = c.keys(p, [[0, 0], [0.22, 1.06], [0.3, 1], [0.7, 1], [1, 0]]), lead = sst(0, 0.1, p) - sst(0.12, 0.3, p);
      o('head', 'ry', -0.62 * e); o('neck', 'ry', -0.15 * e); o('head', 'rz', 0.05 * e);
      o('gazeL', 'ry', -0.25 * lead); o('gazeR', 'ry', -0.25 * lead);
      o('earL', 'ry', -0.2 * e); o('earR', 'ry', -0.2 * e);
      o('ctl', 'look', e);
    } },
    lookRight: { dur: 1.2, fn(p, o, c) {
      const e = c.keys(p, [[0, 0], [0.22, 1.06], [0.3, 1], [0.7, 1], [1, 0]]), lead = sst(0, 0.1, p) - sst(0.12, 0.3, p);
      o('head', 'ry', 0.85 * e); o('neck', 'ry', 0.2 * e); o('head', 'rz', -0.06 * e);
      o('gazeL', 'ry', 0.25 * lead); o('gazeR', 'ry', 0.25 * lead);
      o('earL', 'ry', 0.2 * e); o('earR', 'ry', 0.2 * e);
      o('ctl', 'look', e);
    } },
    rest: { dur: 5.5, fn(p, o, c) { /* breathing slower, lids heavy, the head carried up a little as a resting cat does, the back rounded */
      const e = c.env(p, 0.25, 0.25);
      o('ctl', 'lid', Math.max(0.55 * e, 0.75 * c.bump(p, 0.45, 0.62)));
      o('ctl', 'breath', -0.33 * e); o('ctl', 'amp', 0.5 * e);
      o('chest', 'rx', 0.08 * e); o('neck', 'rx', -0.04 * e); o('head', 'rx', 0.02 * e); o('head', 'py', -0.012 * e);
      o('earL', 'rz', -0.12 * e); o('earR', 'rz', 0.12 * e);
    } },
    dance: { variants: 2, dur: (v) => [2.6, 2.2][v], fn(p, o, c) {
      if (c.v === 0) { /* the pounce-play: the stare, a crouch, the rump treading at 5 Hz, a hop in place landing forepaws first, a settle, then the tail-up greeting and a slow blink */
        const t = p * 2.6;
        look(o, c.keys(t, [[0, 0], [0.08, 1], [2.4, 1], [2.6, 0]]));
        ears(o, -0.26, c.keys(t, [[0, 0], [0.05, 1], [2.2, 1], [2.5, 0]]));
        pupils(o, 1.6 * c.keys(t, [[0, 0], [0.3, 1], [1.45, 1], [2.05, 0]]));
        whisk(o, c.keys(t, [[0, 0], [0.15, 1], [1.5, 1], [2.1, 0]]));
        o('head', 'rx', -0.05 * c.keys(t, [[0, 0], [0.2, 1], [1.4, 1], [1.9, 0]]));
        crouch(o, c.keys(t, [[0, 0], [0.25, 1], [0.95, 1], [1.1, 0.3], [1.45, 0]]));
        const w = bump(t, 0.2, 1.0), ph = c.TAU * 5 * (t - 0.25);
        o('body', 'rz', 0.1 * Math.sin(ph) * w); o('chest', 'rz', -0.06 * Math.sin(ph) * w); o('head', 'rz', -0.035 * Math.sin(ph) * w);
        o('body', 'py', 0.02 * w);
        o('hfootL', 'py', 0.01 * Math.max(0, Math.sin(ph)) * w); o('hfootR', 'py', 0.01 * Math.max(0, -Math.sin(ph)) * w);
        o('tail6', 'ry', 0.25 * Math.sin(c.TAU * 8 * t) * w);
        o('body', 'rx', -0.14 * bump(t, 0.9, 1.35));
        /* in a small hop in place the forelegs tuck (elbows fold, paws hang), then reach down to land first, wrists folding back on the ground */
        for (const L of ['L', 'R']) { o('arm' + L, 'rx', -0.1 * bump(t, 0.95, 1.4)); o('fore' + L, 'rx', -0.55 * bump(t, 0.95, 1.4)); o('paw' + L, 'rx', 0.6 * bump(t, 0.95, 1.33) - 0.25 * bump(t, 1.3, 1.5)); }
        o('mover', 'py', 0.1 * c.hop(t, 1.0, 1.42));
        o('body', 'sy', -0.04 * bump(t, 1.38, 1.52));
        o('chest', 'rx', 0.1 * bump(t, 1.4, 1.62));
        o('body', 'py', c.keys(t, [[1.45, 0], [1.55, -0.015], [1.7, 0.004], [1.85, 0]]));
        /* the tail rises as a wave from the root (segments 50 ms apart) and comes down almost as one, root leading a little */
        tailUp(o, (i) => Math.min(c.keys(t - i * 0.05, [[1.2, 0], [1.6, 1], [2.6, 1]]), c.keys(t - i * 0.02, [[2.0, 1], [2.48, 0]])));
        o('tail6', 'rz', 0.12 * Math.sin(c.TAU * 10 * t) * bump(t, 1.6, 2.1));
        o('ctl', 'lid', c.keys(t, [[1.75, 0], [2.05, 0.82], [2.2, 0.82], [2.55, 0]]));
      } else { /* the greeting: the tail up with a quivering tip, two head bunts as if rubbing a cheek on a hand, a slow blink, the tail down */
        const t = p * 2.2, s = c.r < 0.5 ? 1 : -1;
        look(o, c.keys(t, [[0, 0], [0.1, 1], [2.0, 1], [2.2, 0]]));
        ears(o, -0.22, c.keys(t, [[0, 0], [0.05, 1], [1.9, 1], [2.15, 0]]));
        pupils(o, 0.8 * c.keys(t, [[0, 0], [0.3, 1], [1.5, 1], [2.0, 0]]));
        tailUp(o, (i) => Math.min(c.keys(t - i * 0.04, [[0, 0], [0.3, 1], [2.2, 1]]), c.keys(t - i * 0.02, [[1.5, 1], [2.08, 0]])));
        o('tail6', 'rz', 0.1 * Math.sin(c.TAU * 10 * t) * bump(t, 0.3, 1.2));
        const b1 = bump(t, 0.45, 0.9), b2 = bump(t, 0.9, 1.35);
        o('head', 'rz', s * 0.32 * b1 - s * 0.32 * b2); o('neck', 'pz', 0.05 * (b1 + b2)); o('head', 'rx', 0.12 * (b1 + b2)); o('neck', 'rx', 0.05 * (b1 + b2));
        o('ctl', 'lid', Math.max(0.35 * (b1 + b2), c.keys(t, [[1.3, 0], [1.55, 0.82], [1.7, 0.82], [2.05, 0]])));
      }
    } },
  };
  K.finish(R);
  K.restTurn(R, 'head', [0, HEAD_YAW * 0.75, 0]);      /* bound straight, rests turned toward the reader: the neck bends into the turn */
  K.restTurn(R, 'neck', [0, HEAD_YAW * 0.25, 0]);
  K.restTurn(R, 'eyeLLidLo', [-0.33, 0, 0]);      /* the lower lids sit a little higher: the almond opening of a cat's eye */
  K.restTurn(R, 'eyeRLidLo', [-0.33, 0, 0]);
  return R;
}

export default {
  id: 'cat',
  name: 'Tabby cat',
  latin: 'Felis catus',
  rests: 'floor',
  build: (THREE, kit) => buildCat(THREE, kit),
  update: (rig, dt, state) => rig.kit.update(rig, dt, state),
  play: (rig, clip, variant) => rig.kit.play(rig, clip, variant),
  rest: (rig) => rig.kit.rest(rig),
};
