/*
  The Civic Archive companion: the golden retriever (Canis familiaris), sitting, looking up at the reader.

  Built on the companions' realism kit (kit.js) from the proportions, joint ranges, gaits and habits in
  research/retriever.md (the AKC standard for the build: 12:11 length to height, a 30-degree pelvis, drop ears whose
  tip reaches the eye, a tail to the hock carried level with "merry action"; Hildebrand 1968 and Fischer 2018 for the
  trot and its diagonal pairs; Kano 2016 for the 60 percent front load; Ellis 2018 for the order of a sit, hip then
  stifle then tarsus; Schikowski 2021 for the coupled nod and turn of the neck; Sommese 2022 for the head tilt that is
  always to the same side; Quaranta 2007 for the wag biased to the dog's right; Kaminski 2017 for the inner brow raise
  when a person looks at it; Gahwiler 2020 for ears back as the strongest sign of unease, so the ears here come forward;
  Dickerson 2012 for the 4.5 Hz shake; Koyasu 2022 and Sebbag 2023 for blinks every 4 to 20 seconds, far fewer than
  ours). No licensed model of a retriever exists without a login (research, section 1), so the whole dog is sculpted
  here in code as one signed distance field (a pelvis resting on the floor, folded hind legs with the hocks flat, a deep
  ribcage, straight forelegs, a thick neck with its ruff, a broad skull with a clear stop and a straight muzzle, drop
  ears, a tail curved on the floor, and locks of feathering on the chest, the backs of the forelegs and the thighs)
  surfaced as one mesh that bends over 32 bones; the coat is painted per vertex (a rich golden, paler feathering, a
  darker saddle and ears, a dark nose, dark close-fitting eye rims and lips, dark pads) and dressed in fur shells that
  grow long where the feathering is; the eyes are wet, dark brown with almost no white; the nose is moist leather.
  Nothing is loaded from anywhere.

  export default { id, name, latin, rests, build(THREE, kit) -> rig, update(rig, dt, state), play(rig, clip) -> seconds, rest(rig) }
    rig.root   1 unit = the dog's height sitting (floor to the crown), facing +z toward the reader, paws at y = 0
    rig.frame  the box, in root units, a camera should keep in view
    clips      arrive (trots in from the right on diagonal pairs, turns, and sits hip first), idleA, idleB (an ear
               flick, a sniff bout, a sigh, the sloppy sit, a head shake), notice, react (the head tilt, always to its
               right), talk, lookLeft, lookRight, rest, dance (the merry greeting: play-bow, bounce, shake, sit back and
               look). Every clip ends exactly on the rest pose.
*/

function buildRetriever(THREE, K) {
  if (!K || !K.rig) throw new Error('the retriever needs the companions kit: build(THREE, kit)');
  const { sd, surf, rgb, mixc, fbm, noise, sst, lerp, clamp, unit } = K;
  const PI = Math.PI, TAU = 2 * PI;
  const YAW = -0.55, HEAD_YAW = 0.2, FACE = -(YAW + HEAD_YAW);      /* the body sits turned toward the page; the head rests a little short of the reader */
  const R = K.rig({
    id: 'retriever', yaw: YAW, frame: { x: [-0.47, 0.53], y: [-0.03, 1.08] }, fov: 34,
    breath: 0.33, blinkSpeed: 1.0, look: { yaw: 0.8, pitch: 0.4, speed: 6.5 },
    idles: ['idleA', 'idleB', 'idleB', 'lookLeft', 'lookRight', 'notice'],
  });

  /* ---------- colours (gold near the site's brass, buff, browns and black only) ---------- */
  const GOLD = rgb(0xc7954f), GOLD2 = rgb(0xb07f3f), SADDLE = rgb(0x976a2f), LIGHT = rgb(0xdcb57a), CREAM = rgb(0xefdcb4), CREAM2 = rgb(0xdfc69a);
  const NOSE = rgb(0x17120f), NOSE2 = rgb(0x2b2320), RIM = rgb(0x2a1b12), LIP = rgb(0x3a2819), PAD = rgb(0x3f3028);

  /* ---------- small helpers ---------- */
  const add3 = (a, b) => [a[0] + b[0], a[1] + b[1], a[2] + b[2]];
  const mul3 = (a, k) => [a[0] * k, a[1] * k, a[2] * k];
  const dist3 = (a, b) => Math.hypot(a[0] - b[0], a[1] - b[1], a[2] - b[2]);
  const seg3 = (x, y, z, a, b) => {
    const dx = b[0] - a[0], dy = b[1] - a[1], dz = b[2] - a[2], l2 = dx * dx + dy * dy + dz * dz;
    const t = l2 > 0 ? clamp(((x - a[0]) * dx + (y - a[1]) * dy + (z - a[2]) * dz) / l2, 0, 1) : 0;
    return Math.hypot(x - a[0] - dx * t, y - a[1] - dy * t, z - a[2] - dz * t);
  };
  const along = (P, Q, x, y, z) => { const dx = Q[0] - P[0], dy = Q[1] - P[1], dz = Q[2] - P[2]; return ((x - P[0]) * dx + (y - P[1]) * dy + (z - P[2]) * dz) / (dx * dx + dy * dy + dz * dz); };

  /* ---------- landmarks of the sitting dog (sculpting space; from the standard's proportions with the withers at 0.8) ---------- */
  const SJ = (s) => [s * 0.085, 0.59, 0.24], ELB = (s) => [s * 0.082, 0.38, 0.15], WR = (s) => [s * 0.08, 0.13, 0.15], MC = (s) => [s * 0.08, 0.04, 0.19], FTOE = (s) => [s * 0.082, 0.025, 0.245];
  const HIP = (s) => [s * 0.105, 0.40, -0.10], STIF = (s) => [s * 0.165, 0.27, 0.11], HOCK = (s) => [s * 0.15, 0.03, -0.03], HTOE = (s) => [s * 0.15, 0.024, 0.11];
  const BP = [0, 0.40, -0.10], CP = [0, 0.50, 0.02], NP0 = [0, 0.72, 0.10], NP1 = [0, 0.87, 0.20], HC = [0, 0.905, 0.245];
  const EP = (s) => [s * 0.086, 0.943, 0.21], ET = (s) => [s * 0.14, 0.765, 0.205], E2 = (s) => [s * 0.108, 0.915, 0.205];
  const BR = (s) => [s * 0.04, 0.925, 0.32];
  const T = [[0, 0.30, -0.30], [0.02, 0.21, -0.36], [0.07, 0.12, -0.39], [0.14, 0.055, -0.385], [0.215, 0.032, -0.35], [0.26, 0.028, -0.30], [0.28, 0.026, -0.24]];
  const TR = [0.042, 0.04, 0.036, 0.032, 0.028, 0.023, 0.016];

  /* ---------- the body as fields ---------- */
  const pelvis = sd.egg([0, 0.24, -0.22], [0.165, 0.2, 0.16], [-0.35, 0, 0]);
  const thorax = sd.egg([0, 0.50, 0.02], [0.15, 0.17, 0.2], [-0.65, 0, 0]);
  const brisket = sd.egg([0, 0.50, 0.2], [0.11, 0.15, 0.09]);
  const shoulderF = (s) => sd.egg([s * 0.095, 0.62, 0.15], [0.06, 0.09, 0.08]);
  const withers = sd.egg([0, 0.70, 0.06], [0.1, 0.09, 0.1]);
  const neckF = sd.limb(NP0, NP1, 0.09, 0.075);
  const ruff = sd.egg([0, 0.76, 0.17], [0.1, 0.11, 0.09]);
  const thighF = (s) => sd.add(0.03, sd.limb(HIP(s), STIF(s), 0.1, 0.065), sd.egg([s * 0.13, 0.3, -0.05], [0.07, 0.12, 0.14], [-0.4, 0, 0]));
  const shank = (s) => sd.limb(STIF(s), HOCK(s), 0.05, 0.034);
  const toes = (c, s, n) => { const t = []; for (let i = 0; i < 4; i++) t.push(sd.egg([c[0] + (i - 1.5) * 0.022, c[1], c[2] + n], [0.012, 0.014, 0.022])); return sd.add(0.006, ...t); };
  const hfoot = (s) => sd.add(0.012, sd.limb(HOCK(s), HTOE(s), 0.032, 0.03), sd.egg([s * 0.15, 0.026, 0.085], [0.045, 0.026, 0.06]), toes([s * 0.15, 0.022, 0.12], s, 0));
  const arm = (s) => sd.limb(SJ(s), ELB(s), 0.058, 0.046);
  const fore = (s) => sd.add(0.02, sd.limb(ELB(s), WR(s), 0.044, 0.034), sd.egg([s * 0.085, 0.26, 0.095], [0.03, 0.11, 0.028], [0.1, 0, 0]));      /* the feathering behind the forearm */
  const paw = (s) => sd.add(0.012, sd.limb(WR(s), MC(s), 0.032, 0.03), sd.egg([s * 0.082, 0.028, 0.2], [0.046, 0.028, 0.06]), toes([s * 0.082, 0.023, 0.24], s, 0));
  /* feathering as shape: an apron of locks under the chest, and the pants behind the thighs */
  const apron = sd.add(0.025, sd.egg([0.04, 0.42, 0.27], [0.035, 0.08, 0.03], [-0.2, 0, 0.3]), sd.egg([-0.04, 0.42, 0.27], [0.035, 0.08, 0.03], [-0.2, 0, -0.3]), sd.egg([0, 0.40, 0.29], [0.03, 0.07, 0.028]), sd.egg([0.085, 0.46, 0.245], [0.03, 0.07, 0.03]), sd.egg([-0.085, 0.46, 0.245], [0.03, 0.07, 0.03]));
  const pants = (s) => sd.egg([s * 0.17, 0.17, -0.28], [0.045, 0.1, 0.05], [0.3, 0, s * 0.2]);
  /* the head: a broad, slightly arched skull, a well-defined stop, a straight muzzle nearly as long as the skull, soft flews, a small chin */
  const skull = sd.egg(HC, [0.095, 0.086, 0.1]);
  const occiput = sd.egg([0, 0.89, 0.19], [0.085, 0.08, 0.085]);
  const brow = (s) => sd.egg([s * 0.042, 0.927, 0.3], [0.04, 0.026, 0.036]);
  const muzzle = sd.egg([0, 0.875, 0.42], [0.06, 0.05, 0.096], [0.06, 0, 0]);
  const cheek = (s) => sd.egg([s * 0.056, 0.865, 0.3], [0.052, 0.055, 0.065]);
  const flews = sd.egg([0, 0.845, 0.43], [0.058, 0.036, 0.068]);
  const chin = sd.egg([0, 0.835, 0.44], [0.045, 0.028, 0.06]);
  const headF = sd.add(0.018, sd.add(0.028, skull, occiput, brow(1), brow(-1), cheek(1), cheek(-1)), muzzle, flews, chin);
  /* the eyes: medium large, set well apart at the stop, looking a little outward and up at the reader */
  const EYE_R = 0.024, EYES = [];
  for (const s of [1, -1]) {
    const py = s * 0.5, pp = 0.08, ly = s * 0.3, lp = 0.06;
    const dp = [Math.sin(py) * Math.cos(pp), Math.sin(pp), Math.cos(py) * Math.cos(pp)];
    const dl = [Math.sin(ly) * Math.cos(lp), Math.sin(lp), Math.cos(ly) * Math.cos(lp)];
    const sp = K.hit(headF, [0, 0.905, 0.27], dp), c = add3(sp, mul3(dp, -EYE_R * 0.55));
    EYES.push({ s, c, dl, sp });
  }
  const headS = sd.sub(headF, sd.min(sd.ball(EYES[0].c, EYE_R * 1.12), sd.ball(EYES[1].c, EYE_R * 1.12)), 0.004);
  /* drop ears: a muscular base set just above and behind the eye, a leather that hangs flat on the cheek with its tip at the eye's level */
  const earBase = (s) => sd.egg(EP(s), [0.026, 0.026, 0.038]);
  const earLeaf = (s) => {
    const a = E2(s), b = ET(s), m = [(a[0] + b[0]) / 2, (a[1] + b[1]) / 2, (a[2] + b[2]) / 2], L = dist3(a, b);
    const d = unit([b[0] - a[0], b[1] - a[1], b[2] - a[2]]);
    const rz = Math.asin(clamp(d[0], -1, 1)), rx = Math.atan2(-d[2], -d[1]);      /* the egg's long axis laid along the base-to-tip line */
    return sd.egg(m, [0.02, L / 2 + 0.012, 0.056], [rx, 0, rz]);
  };
  const earF = (s) => sd.add(0.018, earBase(s), earLeaf(s));
  const tailSeg = [];
  for (let i = 0; i < 6; i++) tailSeg.push(sd.limb(T[i], T[i + 1], TR[i], TR[i + 1]));
  const tailF = sd.add(0.018, ...tailSeg);
  const noseS = sd.sub(sd.egg([0, 0.887, 0.5], [0.028, 0.023, 0.021]), sd.min(sd.egg([0.012, 0.884, 0.519], [0.0065, 0.0055, 0.01]), sd.egg([-0.012, 0.884, 0.519], [0.0065, 0.0055, 0.01])), 0.002);

  const trunkF = sd.add(0.07, pelvis, thorax, brisket, withers, shoulderF(1), shoulderF(-1));
  const hind = sd.add(0.03, sd.add(0.055, trunkF, thighF(1), thighF(-1), pants(1), pants(-1)), shank(1), shank(-1), hfoot(1), hfoot(-1));
  const foreQ = sd.add(0.022, sd.add(0.035, hind, neckF, ruff, arm(1), arm(-1), apron), fore(1), fore(-1), paw(1), paw(-1));
  const withHead = sd.add(0.016, sd.add(0.04, foreQ, headS), earF(1), earF(-1));
  const bodyAll = sd.add(0.028, withHead, tailF);
  const all = sd.min(bodyAll, noseS, sd.ball(EYES[0].c, EYE_R), sd.ball(EYES[1].c, EYE_R));

  /* ---------- which part a point belongs to (for the skin weights and the paint) ---------- */
  const PARTS = {
    body: sd.min(pelvis, pants(1), pants(-1)), chest: sd.min(thorax, brisket, withers, shoulderF(1), shoulderF(-1), apron), neck: sd.min(neckF, ruff), head: headS,
    earL: earBase(1), earR: earBase(-1), earL2: earLeaf(1), earR2: earLeaf(-1),
    armL: arm(1), foreL: fore(1), pawL: paw(1), armR: arm(-1), foreR: fore(-1), pawR: paw(-1),
    thighL: thighF(1), shankL: shank(1), hfootL: hfoot(1), thighR: thighF(-1), shankR: shank(-1), hfootR: hfoot(-1),
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
  const member = (name) => { const i = PNAMES.indexOf(name); return (x, y, z) => { const m = partsAt(x, y, z); return Math.exp(-Math.max(0, m.d[i] - m.min) / 0.012); }; };
  const nearest = (x, y, z) => { const m = partsAt(x, y, z); let b = 0; for (let i = 1; i < PFN.length; i++) if (m.d[i] < m.d[b]) b = i; return PNAMES[b]; };

  /* ---------- the coat ---------- */
  function facePaint(x, y, z, nx, ny, nz, c, n) {
    const hx = x - HC[0], hy = y - HC[1], hz = z - HC[2], ax = Math.abs(hx);
    let d = 0;
    for (const E of EYES) {
      const e = E.c, de = Math.hypot(x - e[0], y - e[1], z - e[2]) - EYE_R;
      d = Math.max(d, sst(0.0105, 0.005, de) * sst(-0.004, 0.002, de));      /* the dark, close-fitting rim */
    }
    /* the lips: a dark line where the flews meet the lower jaw, from under the nose back toward the cheek */
    for (const s of [1, -1]) {
      d = Math.max(d, 0.85 * sst(0.006, 0.0025, seg3(hx, hy, hz, [0, -0.045, 0.255], [s * 0.05, -0.05, 0.2])));
      d = Math.max(d, 0.6 * sst(0.006, 0.0025, seg3(hx, hy, hz, [s * 0.05, -0.05, 0.2], [s * 0.066, -0.04, 0.13])));
    }
    d = Math.max(d, 0.6 * sst(0.0035, 0.0015, seg3(hx, hy, hz, [0, -0.02, 0.265], [0, -0.045, 0.255])));      /* the philtrum */
    /* a paler muzzle and throat, a touch darker crown and ears */
    c = mixc(c, mixc(LIGHT, CREAM2, 0.5 * n), 0.55 * sst(0.1, 0.17, hz) * sst(0.02, -0.03, hy));
    c = mixc(c, mixc(CREAM, CREAM2, 0.4 * n), 0.6 * sst(-0.045, -0.085, hy) * sst(0.6, 0.2, Math.abs(Math.atan2(hx, hz + 0.02))));
    c = mixc(c, SADDLE, 0.3 * sst(0.03, 0.08, hy) * sst(0.1, 0.02, hz));
    c = mixc(c, mixc(SADDLE, GOLD2, 0.5), 0.35 * sst(0.06, 0.09, ax) * sst(0.0, 0.05, hy));      /* the temples under the ear base */
    return mixc(c, mixc(RIM, LIP, 0.5), 0.92 * d);
  }
  function coat(x, y, z, nx, ny, nz) {
    const n = fbm(x * 24, y * 24, z * 24, 3), fine = fbm(x * 90, y * 90, z * 90, 2), clump = sst(0.45, 0.8, fbm(x * 40 + 3, y * 40, z * 40, 2));
    let c = mixc(GOLD, GOLD2, 0.25 + 0.5 * n);
    c = mixc(c, LIGHT, 0.3 * sst(0.5, 0.85, fine));
    c = mixc(c, SADDLE, 0.22 * clump);
    const p = nearest(x, y, z);
    if (p === 'head') return facePaint(x, y, z, nx, ny, nz, c, n);
    if (p === 'earL' || p === 'earR' || p === 'earL2' || p === 'earR2') {
      const s = x > 0 ? 1 : -1, inner = sst(0.1, 0.5, -nx * s);      /* the side against the cheek is paler */
      c = mixc(c, mixc(SADDLE, GOLD2, 0.3 + 0.4 * n), 0.72 * (1 - inner));
      return mixc(c, mixc(LIGHT, CREAM2, 0.5), 0.5 * inner + 0.3 * sst(0.84, 0.8, y));      /* the hanging fringe pales toward the tip */
    }
    if (p[0] === 't' && p[1] === 'a') {      /* the tail: darker along the top, cream beneath where the feathering hangs */
      c = mixc(c, SADDLE, 0.25 * sst(0.2, 0.7, ny));
      return mixc(c, mixc(CREAM, CREAM2, 0.5 * n), 0.65 * sst(-0.1, -0.6, ny) + 0.25 * sst(0.0, -0.2, ny));
    }
    if (p === 'pawL' || p === 'pawR' || p === 'hfootL' || p === 'hfootR') {
      c = mixc(c, mixc(LIGHT, CREAM2, 0.5), 0.5 * sst(0.09, 0.03, y));
      return mixc(c, PAD, sst(-0.55, -0.85, ny) * sst(0.04, 0.015, y));      /* the pads */
    }
    if (p === 'foreL' || p === 'foreR' || p === 'armL' || p === 'armR') {
      c = mixc(c, mixc(CREAM, CREAM2, 0.5 * n), 0.55 * sst(0.1, -0.5, nz) * sst(0.4, 0.3, y));      /* the feathering behind the forearm */
      return mixc(c, LIGHT, 0.2 * sst(0.2, 0.7, nz));
    }
    const phi = Math.atan2(Math.abs(x), z + 0.05);      /* 0 at the breast, PI at the spine */
    c = mixc(c, SADDLE, 0.4 * sst(2.0, 2.9, phi) * sst(0.1, 0.4, ny) * sst(0.12, 0.3, y));      /* the saddle along the back */
    c = mixc(c, mixc(CREAM, CREAM2, 0.4 * n), 0.6 * sst(1.0, 0.45, phi) * sst(0.62, 0.52, y) * sst(0.25, 0.35, y));      /* the apron and chest */
    c = mixc(c, mixc(CREAM, CREAM2, 0.5), 0.55 * sst(-0.15, -0.7, ny) * sst(0.5, 0.35, y));      /* the underside and pants */
    if (p === 'body') c = mixc(c, mixc(CREAM, CREAM2, 0.5 * n), 0.4 * sst(0.1, 0.25, Math.abs(x) - 0.12) * sst(0.3, 0.15, y));
    if (p === 'neck') c = mixc(c, mixc(CREAM2, LIGHT, 0.5), 0.35 * sst(1.0, 0.4, phi));      /* the ruff at the front of the neck */
    return c;
  }
  /* the groom: short and even on the head, the paws and the fronts of the legs; a ruff at the throat; long feathering on
     the chest, the backs of the forelegs and thighs and under the tail; combed down and back; none across the eyes or nose */
  function groom(x, y, z, nx, ny, nz) {
    const p = nearest(x, y, z);
    let len = 0.9, cx = 0, cy = -0.7, cz = -0.6;
    if (p === 'head') {
      const hz = z - HC[2], hy = y - HC[1];
      len = lerp(0.32, 0.1, sst(0.05, 0.13, hz));      /* short and even on the skull, smooth on the muzzle */
      for (const E of EYES) len *= sst(0.0, 0.018, Math.hypot(x - E.c[0], y - E.c[1], z - E.c[2]) - EYE_R * 1.25);
      len *= sst(0.0, 0.03, Math.hypot(x, y - 0.887, z - 0.505) - 0.03);
      len *= lerp(1, 1.6, sst(0.05, 0.08, Math.abs(x)) * sst(0.02, -0.03, hy) * sst(0.12, 0.06, hz));      /* the cheeks' longer coat */
      len *= lerp(1, 1.8, sst(-0.04, -0.08, hy));      /* the throat's longer coat begins under the jaw */
      return [len, 1, (x > 0 ? 1 : -1) * 0.4, -0.5, -0.6];
    }
    if (p === 'earL' || p === 'earR') return [0.45, 1, 0, -1, -0.2];
    if (p === 'earL2' || p === 'earR2') { const s = x > 0 ? 1 : -1; return [lerp(0.5, 1.1, sst(0.86, 0.8, y)) * (nx * s > 0 ? 1 : 0.4), 1, s * 0.2, -1, -0.15]; }
    if (p[0] === 't' && p[1] === 'a') {
      let best = Infinity, dir = [0, 0, -1];
      for (let i = 0; i < 6; i++) { const d = seg3(x, y, z, T[i], T[i + 1]); if (d < best) { best = d; dir = unit(add3(T[i + 1], mul3(T[i], -1))); } }
      const under = sst(-0.1, -0.6, ny);
      return [lerp(1.0, 1.7, under), lerp(1, 0.75, under), dir[0] * 0.7, dir[1] * 0.7 - 0.6, dir[2] * 0.7];
    }
    if (p === 'pawL' || p === 'pawR' || p === 'hfootL' || p === 'hfootR') return [0.3, 1, 0, -0.3, 1];
    if (p === 'foreL' || p === 'foreR' || p === 'armL' || p === 'armR') { const back = sst(0.1, -0.5, nz); return [lerp(0.4, 1.5, back) * lerp(1, 0.6, sst(0.2, 0.1, y)), lerp(1, 0.75, back), 0, -1, -0.3 * back]; }
    if (p === 'shankL' || p === 'shankR') return [0.55, 1, 0, -0.6, -0.8];
    const phi = Math.atan2(Math.abs(x), z + 0.05);
    len = 0.9 + 0.6 * sst(1.0, 0.45, phi) * sst(0.64, 0.5, y) * sst(0.25, 0.35, y);      /* the apron */
    len += 0.5 * sst(-0.15, -0.7, ny) * sst(0.5, 0.35, y);      /* under the belly and the pants */
    if (p === 'body') len += 0.4 * sst(0.1, 0.25, Math.abs(x) - 0.12) * sst(0.3, 0.15, y) * sst(-0.15, -0.3, z);
    if (p === 'neck') { len += 0.5 * sst(1.0, 0.4, phi); cz = -0.8; }
    if (p === 'thighL' || p === 'thighR') len += 0.2;
    return [len, len > 1.2 ? 0.75 : 1, cx, cy, cz];      /* the long feathering falls in fewer, thicker locks */
  }

  /* ---------- materials ---------- */
  const furM = K.physical({ rough: 0.72, sheen: 0.55, sheenRough: 0.5, sheenColor: 0xf2dcae, spec: 0.3, name: 'retriever-fur' });
  const noseM = K.physical({ rough: 0.38, clearcoat: 0.55, ccRough: 0.2, spec: 0.6, name: 'retriever-nose' });

  /* ---------- joints (bones): the spine, the drop ears in two parts, the brows, both pairs of legs, the tail chain ---------- */
  K.joint(R, 'body', 'pose', BP);
  K.joint(R, 'chest', 'body', CP);
  K.joint(R, 'neck', 'chest', NP0);
  K.joint(R, 'head', 'neck', NP1);
  for (const s of [1, -1]) {
    const L = s > 0 ? 'L' : 'R';
    K.joint(R, 'ear' + L, 'head', EP(s)); K.joint(R, 'ear' + L + '2', 'ear' + L, E2(s));
    K.joint(R, 'brow' + L, 'head', BR(s));
    K.joint(R, 'arm' + L, 'chest', SJ(s)); K.joint(R, 'fore' + L, 'arm' + L, ELB(s)); K.joint(R, 'paw' + L, 'fore' + L, WR(s));
    K.joint(R, 'thigh' + L, 'body', HIP(s)); K.joint(R, 'shank' + L, 'thigh' + L, STIF(s)); K.joint(R, 'hfoot' + L, 'shank' + L, HOCK(s));
  }
  for (let i = 0; i < 6; i++) K.joint(R, 'tail' + (i + 1), i ? 'tail' + i : 'body', T[i]);
  K.limit(R, 'head', { ry: [-1.1, 1.1], rx: [-0.65, 0.7], rz: [-0.6, 0.6] });
  K.limit(R, 'neck', { ry: [-0.5, 0.5], rx: [-1.0, 0.6] });
  for (const e of ['earL', 'earR']) K.limit(R, e, { rx: [-0.6, 0.6], ry: [-0.5, 0.5], rz: [-0.5, 0.5] });

  /* ---------- the skinned body with its coat ---------- */
  const BONES = [
    { j: 'body', a: [0, 0.1, -0.28], b: [0, 0.38, -0.12], r: 0.26, only: member('body') },
    { j: 'chest', a: [0, 0.38, -0.02], b: [0, 0.68, 0.1], r: 0.26, only: member('chest') },
    { j: 'neck', a: NP0, b: NP1, r: 0.15, only: member('neck') },
    { j: 'head', a: [0, 0.88, 0.2], b: [0, 0.885, 0.46], r: 0.22, only: member('head') },
    { j: 'browL', a: BR(1), b: add3(BR(1), [0, 0.015, -0.01]), r: 0.026 },
    { j: 'browR', a: BR(-1), b: add3(BR(-1), [0, 0.015, -0.01]), r: 0.026 },
  ];
  for (const s of [1, -1]) {
    const L = s > 0 ? 'L' : 'R';
    BONES.push({ j: 'ear' + L, a: EP(s), b: E2(s), r: 0.06, only: member('ear' + L) }, { j: 'ear' + L + '2', a: E2(s), b: ET(s), r: 0.09, only: member('ear' + L + '2') },
      { j: 'arm' + L, a: SJ(s), b: ELB(s), r: 0.09, only: member('arm' + L) }, { j: 'fore' + L, a: ELB(s), b: WR(s), r: 0.09, only: member('fore' + L) },
      { j: 'paw' + L, a: WR(s), b: FTOE(s), r: 0.08, only: member('paw' + L) },
      { j: 'thigh' + L, a: HIP(s), b: STIF(s), r: 0.16, only: member('thigh' + L) }, { j: 'shank' + L, a: STIF(s), b: HOCK(s), r: 0.1, only: member('shank' + L) },
      { j: 'hfoot' + L, a: HOCK(s), b: [s * 0.15, 0.025, 0.14], r: 0.09, only: member('hfoot' + L) });
  }
  for (let i = 0; i < 6; i++) BONES.push({ j: 'tail' + (i + 1), a: T[i], b: T[i + 1], r: 0.08, only: member('tail' + (i + 1)) });
  const bodyGeo = surf(bodyAll, [-0.3, -0.012, -0.47, 0.37, 1.05, 0.56], 0.0115, coat, { ao: all, groom });
  const bodyMesh = K.skin(R, bodyGeo, BONES, furM, { smooth: 3, name: 'retriever-body' });
  K.fur(R, bodyMesh, { len: 0.022, dens: 135, thin: 0.9, root: 0.68, clump: 0.5, comb: 0.9, droop: 0.45, min: 0.4 });

  /* ---------- the nose leather, on the head ---------- */
  K.put(R, 'head', surf(noseS, [-0.034, 0.858, 0.474, 0.034, 0.916, 0.526], 0.0028, (x, y, z) => mixc(NOSE, NOSE2, 0.35 * sst(0.51, 0.52, z) + 0.3 * fbm(x * 200, y * 200, z * 200, 2)), { ao: all }), noseM);

  /* ---------- the eyes: dark brown, wet, almost no white showing; the ball turns inside the lids (gaze joints) ---------- */
  const lidPaint = (lidR) => (x, y) => { const t = y / lidR; return t < 0.1 ? RIM : mixc(RIM, mixc(GOLD2, SADDLE, 0.4), sst(0.1, 0.3, t)); };
  for (const E of EYES) {
    const L = E.s > 0 ? 'L' : 'R', name = 'eye' + L, lidR = EYE_R * 1.1;
    const j = K.eye(R, name, 'head', E.c, E.dl, EYE_R, {
      iris: 0x3a2210, iris2: 0x6e4420, pupil: 0.48, irisAngle: 0.95, sclera: 0x3a2b20, limbal: 0x110906,
      lid: lidPaint(lidR), lidLo: lidPaint(lidR), lidMat: { rough: 0.7, sheen: 0.35, name: name + '-lid' },
      open: -0.75, shut: 1.5, glint: 0.26, glintA: 0.85, lowerShare: 0.3, gloss: 0.6, wet: 0.32, corneaAngle: 1.0,
    });
    const gaze = K.local(R, 'gaze' + L, name, [0, 0, 0]);
    const ball = j.children.find((x) => x.name === name + '-mesh');
    if (ball) gaze.add(ball);
    K.limit(R, 'gaze' + L, { ry: [-0.35, 0.35], rx: [-0.25, 0.25] });
  }

  /* ---------- secondary motion: the ear leathers swing like 3 Hz pendulums; the tail follows a wag through ---------- */
  for (const L of ['L', 'R']) {
    const s = L === 'L' ? 1 : -1;
    K.spring(R, 'ear' + L + '2', { ch: 'rx', k: 355, c: 11, gain: 0.03, dir: [0, -1, 0], lim: [-0.6, 0.6] });
    K.spring(R, 'ear' + L + '2', { ch: 'rz', k: 355, c: 11, gain: 0.03, dir: [0, -1, 0], lim: [s > 0 ? -0.3 : -0.7, s > 0 ? 0.7 : 0.3] });
  }
  const dirOf = (a, b) => unit([b[0] - a[0], b[1] - a[1], b[2] - a[2]]);
  K.spring(R, 'tail3', { ch: 'ry', k: 260, c: 14, gain: 0.04, dir: dirOf(T[2], T[3]), lim: [-0.5, 0.5] });
  K.spring(R, 'tail5', { ch: 'ry', k: 180, c: 10, gain: 0.06, dir: dirOf(T[4], T[5]), lim: [-0.7, 0.7] });
  K.spring(R, 'tail4', { ch: 'rx', k: 200, c: 11, gain: 0.05, dir: dirOf(T[3], T[4]), lim: [-0.5, 0.5] });

  /* ---------- poses: the legs are solved, never guessed. Every leg joint turns about x (the sagittal plane), so a bone's
     direction is an angle psi = atan2(dy, dz); turning a parent by theta lowers every child's psi by theta. The thigh and
     shank (or arm and forearm) meet the hock (or carpus) target by two circles; the foot bone then aims at the toes ---------- */
  const psi = (a, b) => Math.atan2(b[1] - a[1], b[2] - a[2]);
  const len2 = (a, b) => Math.hypot(b[1] - a[1], b[2] - a[2]);
  const rotYZ = (y, z, th) => [y * Math.cos(th) - z * Math.sin(th), y * Math.sin(th) + z * Math.cos(th)];
  function knee(h, t, L1, L2, fwd) {      /* h, t: [y, z]; returns [knee [y, z], reachable target [y, z]] */
    let dy = t[0] - h[0], dz = t[1] - h[1], d0 = Math.hypot(dy, dz) || 1e-6;
    const d = clamp(d0, Math.abs(L1 - L2) + 1e-4, L1 + L2 - 1e-4), uy = dy / d0, uz = dz / d0;
    const a = (L1 * L1 - L2 * L2 + d * d) / (2 * d), hh = Math.sqrt(Math.max(0, L1 * L1 - a * a));
    const my = h[0] + a * uy, mz = h[1] + a * uz, py = -uz, pz = uy;
    const k1 = [my + hh * py, mz + hh * pz], k2 = [my - hh * py, mz - hh * pz];
    const k = fwd > 0 ? (k1[1] >= k2[1] ? k1 : k2) : (k1[1] < k2[1] ? k1 : k2);
    return [k, [h[0] + d * uy, h[1] + d * uz]];
  }
  const LEG = {};
  for (const s of [1, -1]) {
    const L = s > 0 ? 'L' : 'R';
    LEG[L] = {
      h: { L1: len2(HIP(s), STIF(s)), L2: len2(STIF(s), HOCK(s)), p1: psi(HIP(s), STIF(s)), p2: psi(STIF(s), HOCK(s)), p3: psi(HOCK(s), HTOE(s)) },
      f: { L1: len2(SJ(s), ELB(s)), L2: len2(ELB(s), WR(s)), p1: psi(SJ(s), ELB(s)), p2: psi(ELB(s), WR(s)), p3: psi(WR(s), FTOE(s)) },
    };
  }
  /* a hind leg from the hip's world [y, z]: toe and hock targets as [y, z offset from the hip's z]; par is the parents' x turn */
  function hindLeg(o, L, w, hipW, toe, hock, par) {
    const G = LEG[L].h, tk = [hock[0], hipW[1] + hock[1]], tt = [toe[0], hipW[1] + toe[1]];
    const [k, tr] = knee(hipW, tk, G.L1, G.L2, 1);
    const a1 = G.p1 - Math.atan2(k[0] - hipW[0], k[1] - hipW[1]) - par;
    const a2 = G.p2 - Math.atan2(tr[0] - k[0], tr[1] - k[1]) - par - a1;
    const a3 = G.p3 - Math.atan2(tt[0] - tr[0], tt[1] - tr[1]) - par - a1 - a2;
    o('thigh' + L, 'rx', a1 * w); o('shank' + L, 'rx', a2 * w); o('hfoot' + L, 'rx', a3 * w);
  }
  function foreLeg(o, L, w, sjW, wr, toe, par) {
    const G = LEG[L].f, tw = [wr[0], sjW[1] + wr[1]], tt = [toe[0], sjW[1] + toe[1]];
    const [k, tr] = knee(sjW, tw, G.L1, G.L2, -1);
    const a1 = G.p1 - Math.atan2(k[0] - sjW[0], k[1] - sjW[1]) - par;
    const a2 = G.p2 - Math.atan2(tr[0] - k[0], tr[1] - k[1]) - par - a1;
    const a3 = G.p3 - Math.atan2(tt[0] - tr[0], tt[1] - tr[1]) - par - a1 - a2;
    o('arm' + L, 'rx', a1 * w); o('fore' + L, 'rx', a2 * w); o('paw' + L, 'rx', a3 * w);
  }
  /* a whole-body pose P: by, bz the pelvis's move; brx its turn; cat the chest pivot's world [y, z] (or null: carried); crx
     the chest's own turn; hind[L/R] = {toe:[y, dz], hock:[y, dz]} from the hip; fore[L/R] = {wr:[y, dz], toe:[y, dz]} from the
     shoulder joint; level how much the neck and head undo the trunk's tilt */
  const SJd = [SJ(1)[1] - CP[1], SJ(1)[2] - CP[2]], CPd = [CP[1] - BP[1], CP[2] - BP[2]];
  const REST = { by: 0, bz: 0, brx: 0, cat: null, crx: 0, level: 1,
    hind: { toe: [HTOE(1)[1], HTOE(1)[2] - HIP(1)[2]], hock: [HOCK(1)[1], HOCK(1)[2] - HIP(1)[2]] }, fore: { wr: [WR(1)[1], WR(1)[2] - SJ(1)[2]], toe: [FTOE(1)[1], FTOE(1)[2] - SJ(1)[2]] } };
  const STAND = { by: 0.15, bz: -0.016, brx: 0.8, cat: null, crx: -0.3, level: 1, hind: { toe: [0.025, -0.184], hock: [0.14, -0.234] }, fore: { wr: [0.13, -0.05], toe: [0.025, 0.045] } };
  const BOW = { by: 0.2, bz: 0.0, brx: 1.25, cat: [0.28, 0.17], crx: 0.35, level: 1.05, hind: { toe: [0.024, 0.21], hock: [0.135, 0.16] }, fore: { wr: [0.045, 0.23], toe: [0.025, 0.32] } };
  const lerpP = (A, B, t) => ({
    by: lerp(A.by, B.by, t), bz: lerp(A.bz, B.bz, t), brx: lerp(A.brx, B.brx, t), crx: lerp(A.crx, B.crx, t), level: lerp(A.level, B.level, t),
    cat: A.cat || B.cat ? [lerp(A.cat ? A.cat[0] : NaN, B.cat ? B.cat[0] : NaN, t), lerp(A.cat ? A.cat[1] : NaN, B.cat ? B.cat[1] : NaN, t)] : null,
    hind: { toe: [lerp(A.hind.toe[0], B.hind.toe[0], t), lerp(A.hind.toe[1], B.hind.toe[1], t)], hock: [lerp(A.hind.hock[0], B.hind.hock[0], t), lerp(A.hind.hock[1], B.hind.hock[1], t)] },
    fore: { wr: [lerp(A.fore.wr[0], B.fore.wr[0], t), lerp(A.fore.wr[1], B.fore.wr[1], t)], toe: [lerp(A.fore.toe[0], B.fore.toe[0], t), lerp(A.fore.toe[1], B.fore.toe[1], t)] },
  });
  const carried = (P) => { const r = rotYZ(CPd[0], CPd[1], P.brx); return [BP[1] + P.by + r[0], BP[2] + P.bz + r[1]]; };      /* where the chest pivot is carried to */
  function trunk(o, P, w = 1, legs) {
    if (w <= 0) return;
    o('body', 'py', P.by * w); o('body', 'pz', P.bz * w); o('body', 'rx', P.brx * w); o('chest', 'rx', P.crx * w);
    let cpw = carried(P);
    if (P.cat && !isNaN(P.cat[0])) {      /* the spine flexes: the chest pivot is moved in the pelvis's frame to where it is asked */
      const d = rotYZ(P.cat[0] - cpw[0], P.cat[1] - cpw[1], -P.brx);
      o('chest', 'py', d[0] * w); o('chest', 'pz', d[1] * w); cpw = P.cat;
    }
    const tilt = P.brx + P.crx;
    o('neck', 'rx', -0.55 * tilt * P.level * w); o('head', 'rx', -0.45 * tilt * P.level * w);
    const sj = rotYZ(SJd[0], SJd[1], tilt), sjW = [cpw[0] + sj[0], cpw[1] + sj[1]], hipW = [BP[1] + P.by, BP[2] + P.bz];
    for (const L of ['L', 'R']) {
      const g = legs && legs[L];
      hindLeg(o, L, w, hipW, g && g.toe || P.hind.toe, g && g.hock || P.hind.hock, P.brx);
      foreLeg(o, L, w, sjW, g && g.wr || P.fore.wr, g && g.ftoe || P.fore.toe, tilt);
    }
    R.lastSJ = sjW;
  }

  /* ---------- the tail raised: turns that stand each segment at a chosen elevation (level and "merry", or up in the bow) ---------- */
  const tailTurns = (elev, extra) => {
    const Q = new THREE.Quaternion(), out = [];
    for (let i = 0; i < 6; i++) {
      const seg = new THREE.Vector3(T[i + 1][0] - T[i][0], T[i + 1][1] - T[i][1], T[i + 1][2] - T[i][2]).normalize();
      const e = elev[i] + extra, target = new THREE.Vector3(0, Math.sin(e), -Math.cos(e));
      const tl = target.applyQuaternion(Q.clone().invert());
      const q = new THREE.Quaternion().setFromUnitVectors(seg, tl);
      out.push(q); Q.multiply(q);
    }
    return out;
  };
  /* the tail points back, so when the pelvis turns forward by brx the tail rises by brx: the body-frame elevation is the wanted one less brx */
  const TAIL_STAND = tailTurns([0.25, 0.18, 0.1, 0.02, -0.05, -0.1], -STAND.brx), TAIL_BOW = tailTurns([0.55, 0.5, 0.45, 0.4, 0.35, 0.3], -BOW.brx), TAIL_HAPPY = tailTurns([0.45, 0.35, 0.22, 0.1, 0, -0.08], 0);
  const Q0 = new THREE.Quaternion(), QT = new THREE.Quaternion(), ET3 = new THREE.Euler();
  const tailPose = (o, Q, kOf) => {
    for (let i = 0; i < 6; i++) {
      const k = clamp(typeof kOf === 'function' ? kOf(i) : kOf, 0, 1);
      if (k <= 0) continue;
      QT.copy(Q0).slerp(Q[i], k); ET3.setFromQuaternion(QT, 'XYZ');
      o('tail' + (i + 1), 'rx', ET3.x); o('tail' + (i + 1), 'ry', ET3.y); o('tail' + (i + 1), 'rz', ET3.z);
    }
  };
  /* the wag: a wave from the base to the tip, each segment lagging the one before; bias to the dog's right (+ry) when happy;
     heli adds the "helicopter" circle at the tip */
  const wag = (o, t, hz, amp, bias, k, heli = 0) => {
    if (k <= 0) return;
    for (let i = 1; i <= 6; i++) {
      const ph = TAU * hz * t - 0.52 * (i - 1);
      o('tail' + i, 'ry', k * (bias * (i <= 2 ? 0.5 : 0.1) + amp * (0.2 + 0.14 * i) * Math.sin(ph)));
      if (heli && i >= 3) o('tail' + i, 'rx', k * heli * amp * 0.12 * i * Math.cos(ph));
    }
  };
  const ears = (o, fwd, e) => { if (e) { o('earL', 'rx', -fwd * e); o('earR', 'rx', -fwd * e); o('earL', 'rz', 0.12 * fwd * e); o('earR', 'rz', -0.12 * fwd * e); } };
  const brows = (o, e) => { if (e) { o('browL', 'py', 0.008 * e); o('browR', 'py', 0.008 * e); o('eyeLLid', 'rx', -0.12 * e); o('eyeRLid', 'rx', -0.12 * e); } };
  const look = (o, e) => { if (e) { o('head', 'ry', FACE * 0.7 * e); o('neck', 'ry', FACE * 0.3 * e); o('ctl', 'look', e); } };
  const gaze = (o, y, p) => { o('gazeL', 'ry', y); o('gazeR', 'ry', y); o('gazeL', 'rx', p); o('gazeR', 'rx', p); };
  /* the wet-dog shake, 4.5 Hz (Dickerson 2012): it starts at the head and runs back; the ears flap a beat behind */
  const shake = (o, t, t0, cycles, A, w) => {
    if (w <= 0) return;
    const ph = TAU * 4.5 * (t - t0);
    o('head', 'ry', A * Math.sin(ph) * w); o('head', 'rz', 0.25 * A * Math.sin(ph - 0.5) * w);
    o('neck', 'ry', 0.45 * A * Math.sin(ph - 0.35) * w); o('chest', 'ry', 0.18 * A * Math.sin(ph - 0.7) * w); o('body', 'rz', 0.1 * A * Math.sin(ph - 0.9) * w);
    o('earL2', 'rx', 0.9 * Math.sin(ph - 0.45) * w); o('earR2', 'rx', -0.9 * Math.sin(ph - 0.45) * w);
    o('earL2', 'rz', 0.5 * Math.abs(Math.sin(ph - 0.6)) * w); o('earR2', 'rz', -0.5 * Math.abs(Math.sin(ph - 0.6)) * w);
    o('earL', 'rz', 0.2 * Math.abs(Math.sin(ph - 0.3)) * w); o('earR', 'rz', -0.2 * Math.abs(Math.sin(ph - 0.3)) * w);
  };

  /* ---------- the gait: a trot on diagonal pairs (LH with RF, then RH with LF), duty 0.45, the planted foot held to its spot
     on the page by the mover's own path, the swinging foot carried forward in an arc (Hildebrand 1968; Fischer 2018) ---------- */
  const TROT = { L: { h: 0.0, f: 0.5 }, R: { h: 0.5, f: 0.0 } };
  function gait(t, xOf, cfg) {
    const { hz, duty, stride } = cfg, out = {}, Pd = 1 / hz;
    const foot = (off, ahead) => {
      const c = t * hz - off, i = Math.floor(c), u = c - i, tl = Math.max(0, (i + off) * Pd), m0 = xOf(tl);
      if (u < duty) return { z: ahead + xOf(t) - m0, lift: 0 };
      const toff = tl + duty * Pd, zoff = ahead + xOf(Math.min(t, toff)) - m0, v = (u - duty) / (1 - duty), sm = v * v * (3 - 2 * v);
      return { z: lerp(zoff, ahead, sm), lift: Math.sin(PI * v) };
    };
    for (const L of ['L', 'R']) {
      const h = foot(TROT[L].h, stride * 0.5), f = foot(TROT[L].f, stride * 0.5);
      out[L] = {
        toe: [0.025 + 0.06 * h.lift, STAND.hind.toe[1] + 0.03 + h.z], hock: [0.14 + 0.07 * h.lift, STAND.hind.toe[1] + 0.03 + h.z - 0.05 - 0.04 * h.lift],
        wr: [0.13 + 0.07 * f.lift, STAND.fore.wr[1] + f.z - 0.02 * f.lift], ftoe: [0.025 + 0.05 * f.lift, STAND.fore.toe[1] + f.z + 0.02 * f.lift],
      };
    }
    return out;
  }

  /* ---------- breathing, attention and the small habits that never stop (deterministic from the clock) ---------- */
  const hsh = (i, k) => { let h = Math.imul(i | 0, 0x27d4eb2d) ^ Math.imul((k | 0) + 1, 0x165667b1); h = Math.imul(h ^ (h >>> 15), 0x2c1b3c6d); h ^= h >>> 12; return (h >>> 0) / 4294967296; };
  const ev = (t, period, k) => { const i = Math.floor(t / period); return { u: t - (i + 0.7 * hsh(i, k)) * period, i }; };
  const bump = (u, a, b) => { if (u <= a || u >= b) return 0; const s = Math.sin((PI * (u - a)) / (b - a)); return s * s; };
  R.spec.life = (o, L) => {
    const t = L.t, sigh = 1 + 0.7 * sst(0.85, 1, Math.sin(t * 0.08 + 0.7)), b = L.b * sigh;
    /* breathing at about 20 a minute: the ribs widen, the belly moves more than the chest, the shoulders and head lift a hair */
    o('chest', 'sx', 0.016 * b); o('chest', 'sz', 0.012 * b); o('chest', 'sy', 0.003 * b);
    o('body', 'sx', 0.013 * b); o('body', 'sz', 0.008 * b);
    o('neck', 'py', 0.002 * b); o('head', 'rx', -0.005 * b);
    o('armL', 'rz', -0.006 * b); o('armR', 'rz', 0.006 * b);
    if (L.still) return;
    /* a dog blinks every 4 to 20 seconds (Koyasu 2022; Sebbag 2023), more when watched: the kit's gap is stretched once per blink */
    if (R.blinkT >= 0) { if (!R.stretched && !R.blinkAgain) { R.stretched = true; R.nextBlink += (R.look.px != null ? 1.2 : 2.5) + R.rnd() * 6; } } else R.stretched = false;
    /* attention: the head turns with the neck taking a share and the chest leaning (60 percent of the weight is on the forelegs);
       the eyes reach first and come back as the head arrives; a turn carries a little roll (Schikowski 2021) */
    const k = 1 - Math.min(1, R.ctl.look), gapY = R.look.ty * k - L.yaw, gapP = R.look.tp * k - L.pitch;
    o('head', 'ry', 0.65 * L.yaw); o('neck', 'ry', 0.27 * L.yaw); o('chest', 'ry', 0.08 * L.yaw);
    o('head', 'rx', 0.7 * L.pitch); o('neck', 'rx', 0.3 * L.pitch); o('head', 'rz', -0.1 * L.yaw);
    o('body', 'rz', 0.03 * L.yaw);
    const att = clamp(Math.abs(L.yaw) / 0.3 + Math.abs(gapY) / 0.2 + Math.abs(L.pitch) / 0.25, 0, 1);
    const fx = ev(t, 3.1, 6), prevY = (hsh(fx.i - 1, 7) - 0.5) * 0.22, nowY = (hsh(fx.i, 7) - 0.5) * 0.22, prevP = (hsh(fx.i - 1, 8) - 0.5) * 0.12, nowP = (hsh(fx.i, 8) - 0.5) * 0.12;
    const fw = sst(0, 0.08, fx.u), fixY = lerp(prevY, nowY, fw) * (1 - att), fixP = lerp(prevP, nowP, fw) * (1 - att);
    gaze(o, clamp(0.8 * gapY, -0.3, 0.3) + fixY, clamp(0.8 * gapP, -0.2, 0.2) + fixP);
    /* the ears come forward and lift when it is engaged (never back: that is the sign of fear, Gahwiler 2020) */
    ears(o, 0.28, att);
    o('earL', 'ry', 0.15 * clamp(R.look.ty * k, -0.5, 0.5)); o('earR', 'ry', 0.15 * clamp(R.look.ty * k, -0.5, 0.5));
    /* the inner brow raise, about twice as often when a person is looking (Kaminski 2017): every 10 to 20 seconds, 0.8 s */
    const br = ev(t, 14, 3), brw = sst(0, 0.2, br.u) * (1 - sst(0.5, 0.9, br.u));
    brows(o, brw * (0.35 + 0.65 * att));
    /* the tail on the floor: the tip twitches once in a while, the whole tail drifts a little */
    const tl = ev(t, 7, 4), tw = bump(tl.u, 0, 0.35);
    o('tail6', 'ry', 0.3 * tw * (hsh(tl.i, 5) > 0.5 ? 1 : -1)); o('tail5', 'ry', 0.1 * tw);
    o('tail5', 'rx', -0.15 * bump(tl.u, 0, 1.2) * (hsh(tl.i, 9) > 0.6 ? 1 : 0));
    o('tail4', 'ry', 0.03 * Math.sin(t * 0.6)); o('tail6', 'ry', 0.04 * Math.sin(t * 0.9 + 1));
    o('earL2', 'rz', 0.02 * Math.sin(t * 0.5)); o('earR2', 'rz', -0.02 * Math.sin(t * 0.45 + 2));
  };
  R.spec.duck = (o, d) => { o('mover', 'px', 0.34 * d); o('pose', 'ry', 0.4 * d); o('head', 'rx', 0.1 * d); o('earL', 'rx', 0.15 * d); o('earR', 'rx', 0.15 * d); };

  /* ---------- clips (durations from research 2.10; every one ends exactly at rest) ---------- */
  const xArrive = (t) => { const u = Math.min(1, t / 1.3); return 1.45 * (1 - u) * (1 - u); };
  const TURN0 = -PI / 2 - YAW;      /* facing the way it travels (screen left), as a turn from the rest yaw */
  R.clips = {
    arrive: { dur: 2.0, fn(p, o, c) { /* trots in from the right on diagonal pairs with the head nodding and the tail streaming level, slows to two walking steps as it turns to the reader, then sits: hind feet under, hips, stifles, hocks folding in that order, the rump landing with a small settle (Ellis 2018), one blink on landing */
      if (p >= 1) return;
      const t = p * 2;
      o('mover', 'px', xArrive(t));
      o('pose', 'ry', TURN0 * (1 - c.ramp(t, 1.0, 1.5)));
      const q = c.ramp(t, 1.3, 1.95), gw = 1 - c.ramp(t, 1.15, 1.4);
      const P = lerpP(STAND, REST, q);
      let legs = null;
      if (gw > 0) {
        const G = gait(t, xArrive, { hz: 2.5, duty: 0.45, stride: 0.5 });
        legs = {};
        for (const L of ['L', 'R']) legs[L] = { toe: [lerp(P.hind.toe[0], G[L].toe[0], gw), lerp(P.hind.toe[1], G[L].toe[1], gw)], hock: [lerp(P.hind.hock[0], G[L].hock[0], gw), lerp(P.hind.hock[1], G[L].hock[1], gw)],
          wr: [lerp(P.fore.wr[0], G[L].wr[0], gw), lerp(P.fore.wr[1], G[L].wr[1], gw)], ftoe: [lerp(P.fore.toe[0], G[L].toe[0], gw), lerp(P.fore.toe[1], G[L].toe[1], gw)] };
      } else if (q < 1) {      /* the sit: each hind foot steps forward under the body in turn, the hocks fold flat last */
        legs = {};
        for (const L of ['L', 'R']) {
          const st = c.ramp(t, L === 'L' ? 1.3 : 1.42, L === 'L' ? 1.52 : 1.64), fold = c.ramp(t, 1.45, 1.95), lift = Math.sin(PI * st) * 0.05;
          const tz = lerp(STAND.hind.toe[1], REST.hind.toe[1], st * st * (3 - 2 * st));
          const hk = [lerp(0.115, REST.hind.hock[0] - REST.hind.toe[0], fold), lerp(-0.05, REST.hind.hock[1] - REST.hind.toe[1], fold)];
          const pl = c.ramp(t, L === 'L' ? 1.5 : 1.6, L === 'L' ? 1.6 : 1.7), plift = Math.sin(PI * pl) * 0.02;
          legs[L] = { toe: [0.025 + lift, tz], hock: [0.025 + lift + hk[0] + 0.03 * Math.sin(PI * st), tz + hk[1]], wr: [P.fore.wr[0] + plift, P.fore.wr[1]], ftoe: [P.fore.toe[0] + plift, P.fore.toe[1]] };
        }
      }
      trunk(o, P, 1, legs);
      o('body', 'py', -0.012 * c.bump(t, 1.86, 2.0));
      /* the trot's bounce, nod and crabbing; the tail level with a swing, then a 3 Hz wag to its right as it turns and sits */
      const tr = gw * (1 - c.ramp(t, 0.95, 1.3)) + gw * 0.4 * c.ramp(t, 0.95, 1.3), ph = TAU * 5 * t;
      o('body', 'py', 0.012 * Math.sin(ph) * tr); o('head', 'rx', 0.05 * Math.sin(ph + 0.6) * tr); o('neck', 'rx', 0.02 * Math.sin(ph + 0.6) * tr);
      o('body', 'ry', 0.05 * tr); o('chest', 'ry', 0.03 * Math.sin(ph * 0.5) * tr); o('body', 'rz', 0.025 * Math.sin(ph * 0.5) * tr);
      tailPose(o, TAIL_STAND, (i) => (1 - q) * (1 - 0.3 * c.ramp(t, 1.0, 1.4)));
      wag(o, t, 3, 0.5, 0.25, c.keys(t, [[0.9, 0], [1.1, 1], [1.75, 1], [1.95, 0]]));
      o('tail3', 'ry', 0.15 * Math.sin(ph * 0.5) * tr);
      /* the head leads the turn to the reader; ears forward; a blink as the rump lands */
      look(o, c.keys(t, [[1.0, 0], [1.4, 1], [1.8, 1], [2.0, 0]]));
      o('ctl', 'look', 1 - c.ramp(t, 1.7, 2.0));
      ears(o, 0.3, c.keys(t, [[0.8, 0], [1.1, 1], [1.8, 1], [2.0, 0]]));
      o('ctl', 'lid', c.bump(t, 1.85, 1.98));
    } },
    idleA: { dur: 5, fn(p, o, c) { /* a deeper breath, one slow sweep of the tail across the floor, a double blink, a shift of weight at the end */
      o('ctl', 'amp', 0.9 * c.bump(p, 0.1, 0.7));
      const e = c.env(p, 0.2, 0.3);
      wag(o, p * 5, 1, 0.3, 0, e * c.bump(p, 0.15, 0.65));
      o('ctl', 'lid', Math.max(c.bump(p, 0.5, 0.56), c.bump(p, 0.58, 0.64)));
      const sh = c.keys(p, [[0.72, 0], [0.84, 1], [1, 0]]);
      o('body', 'rz', 0.05 * sh); o('chest', 'rz', 0.02 * sh); o('head', 'rz', -0.05 * sh);
      o('pawL', 'py', 0.012 * c.bump(p, 0.74, 0.86)); o('foreL', 'rx', -0.1 * c.bump(p, 0.74, 0.86));
      o('head', 'rx', 0.03 * c.bump(p, 0.3, 0.9));
    } },
    idleB: { variants: 5, dur: (v) => [0.9, 1.6, 2.0, 2.8, 0.9][v], fn(p, o, c) {
      if (c.v === 0) { /* an ear flick: one ear base back and forward twice in 0.2 s, the head twitching the other way */
        const s = c.r < 0.5 ? 1 : -1, e = s > 0 ? 'earL' : 'earR', f = c.bump(p, 0.1, 0.32) + 0.8 * c.bump(p, 0.4, 0.62);
        o(e, 'rx', 0.45 * f); o(e, 'rz', s * 0.3 * f); o(e + '2', 'rz', s * 0.25 * f);
        o('head', 'rz', -s * 0.04 * c.bump(p, 0.08, 0.7)); o('head', 'ry', -s * 0.03 * c.bump(p, 0.08, 0.7));
      } else if (c.v === 1) { /* a sniff bout: the nose lifts 12 degrees and makes 5 Hz micro-nods for 0.9 s (Craven 2010), then a swallow */
        const e = c.keys(p, [[0, 0], [0.18, 1], [0.7, 1], [0.9, 0], [1, 0]]);
        o('head', 'rx', -0.21 * e); o('neck', 'rx', -0.06 * e); o('neck', 'pz', 0.012 * e);
        o('head', 'rx', 0.035 * Math.sin(c.TAU * 8 * p) * c.bump(p, 0.18, 0.72));
        o('head', 'rx', 0.12 * c.bump(p, 0.78, 0.98)); o('head', 'py', -0.006 * c.bump(p, 0.78, 0.98));
        ears(o, 0.15, e); o('ctl', 'look', e);
      } else if (c.v === 2) { /* a sigh: one breath at one and a half times the depth, a slow exhale, the head and shoulders settling a centimetre */
        const inh = c.keys(p, [[0, 0], [0.3, 1], [0.5, -0.25], [0.8, -0.1], [1, 0]]);
        o('chest', 'sx', 0.03 * inh); o('chest', 'sz', 0.02 * inh); o('body', 'sx', 0.02 * inh); o('neck', 'py', 0.012 * inh); o('chest', 'py', 0.006 * inh);
        o('head', 'rx', 0.1 * c.keys(p, [[0.3, 0], [0.55, 1], [1, 0]])); o('head', 'py', -0.01 * c.keys(p, [[0.3, 0], [0.55, 1], [1, 0]]));
        o('ctl', 'lid', 0.4 * c.bump(p, 0.35, 0.95));
        ears(o, -0.08, c.bump(p, 0.3, 1));
      } else if (c.v === 3) { /* the sloppy sit: the trunk rolls onto one hip and a hind leg slides out, then it straightens up */
        const e = c.keys(p, [[0, 0], [0.28, 1], [0.72, 1], [1, 0]]), s = -1;      /* onto its left hip, the side toward the reader */
        o('body', 'rz', s * 0.17 * e); o('body', 'py', -0.015 * e); o('chest', 'rz', -s * 0.06 * e); o('head', 'rz', -s * 0.12 * e); o('neck', 'rz', -s * 0.03 * e);
        o('thighR', 'ry', -0.35 * e); o('thighR', 'rz', -0.15 * e); o('shankR', 'rx', 0.2 * e); o('hfootR', 'rz', -0.3 * e);
        o('pawL', 'px', 0.02 * e); o('armL', 'rz', 0.06 * e); o('armR', 'rz', 0.04 * e);
        for (let i = 1; i <= 6; i++) o('tail' + i, 'ry', 0.06 * e);
        o('ctl', 'lid', 0.25 * c.bump(p, 0.2, 0.8));
      } else { /* a head shake: three cycles at 4.5 Hz, the ears flapping behind the beat, eyes shut for the middle one */
        const w = c.bump(p, 0.05, 0.85);
        shake(o, p * 0.9, 0.09, 3, 0.42, w);
        o('ctl', 'lid', c.bump(p, 0.3, 0.6));
        o('head', 'rx', 0.08 * c.bump(p, 0.75, 1));
      }
    } },
    notice: { dur: 1.2, fn(p, o, c) { /* the eyes lead by 80 ms, the head turns to the reader in 0.3 s with a touch of roll, the ears come forward, the brows lift; hold; ease back */
      const e = c.keys(p, [[0, 0], [0.06, 0], [0.3, 1.06], [0.37, 1], [0.75, 1], [1, 0]]), lead = sst(0, 0.07, p) - sst(0.1, 0.32, p);
      look(o, e);
      gaze(o, 0.3 * lead * Math.sign(FACE), 0.05 * lead);
      o('head', 'rz', 0.09 * e); o('head', 'rx', -0.06 * e); o('neck', 'rx', -0.04 * e);
      ears(o, 0.32, c.keys(p, [[0, 0], [0.04, 0], [0.2, 1], [0.78, 1], [1, 0]]));
      brows(o, c.keys(p, [[0.2, 0], [0.4, 1], [0.8, 1], [1, 0]]));
      o('ctl', 'breath', -0.6 * c.bump(p, 0, 0.5));
    } },
    react: { dur: 1.5, fn(p, o, c) { /* the head tilt, always to its right (Sommese 2022): 28 degrees in 0.25 s, nose up a touch, ears forward, eyes on the reader; held 0.9 s with a soft wag; back in 0.35 s */
      const f = c.keys(p, [[0, 0], [0.1, 1], [0.85, 1], [1, 0]]), tilt = c.keys(p, [[0.03, 0], [0.2, 1.05], [0.26, 1], [0.76, 1], [1, 0]]);
      look(o, f);
      o('head', 'rz', 0.49 * tilt); o('head', 'rx', -0.09 * tilt); o('neck', 'rz', 0.06 * tilt);
      o('eyeLLid', 'rz', -0.1 * tilt); o('eyeRLid', 'rz', -0.1 * tilt);
      ears(o, 0.33, c.keys(p, [[0, 0], [0.15, 1], [0.8, 1], [1, 0]]));
      brows(o, c.keys(p, [[0.1, 0], [0.3, 1], [0.8, 1], [1, 0]]));
      wag(o, p * 1.5, 3, 0.35, 0.3, c.keys(p, [[0.2, 0], [0.35, 1], [0.8, 1], [1, 0]]));
      tailPose(o, TAIL_HAPPY, (i) => 0.35 * c.keys(p, [[0.2, 0], [0.4, 1], [0.8, 1], [1, 0]]));
    } },
    talk: { dur: 3, fn(p, o, c) { /* attentive: ears forward, a nod every second with a little roll, a soft 2.5 Hz wag to its right, the brows raised once */
      const e = c.env(p, 0.12, 0.2);
      look(o, 0.9 * e);
      o('head', 'rx', (0.07 * Math.sin(c.TAU * 3 * p) - 0.03) * e); o('head', 'rz', 0.05 * Math.sin(c.TAU * p) * e);
      ears(o, 0.25, e);
      brows(o, c.bump(p, 0.35, 0.65));
      wag(o, p * 3, 2.5, 0.35, 0.3, e);
      tailPose(o, TAIL_HAPPY, (i) => 0.3 * e);
      o('ctl', 'lid', 0.25 * c.bump(p, 0.7, 0.78));
    } },
    lookLeft: { dur: 1.0, fn(p, o, c) { /* the eyes lead, the head turns 45 degrees with the body leaning a little the same way; the ear on that side comes forward */
      const e = c.keys(p, [[0, 0], [0.26, 1.05], [0.34, 1], [0.7, 1], [1, 0]]), lead = sst(0, 0.08, p) - sst(0.1, 0.3, p);
      o('head', 'ry', -0.55 * e); o('neck', 'ry', -0.2 * e); o('chest', 'ry', -0.07 * e); o('head', 'rz', 0.06 * e);
      gaze(o, -0.3 * lead, 0);
      o('earR', 'rx', -0.25 * e); o('earR', 'ry', -0.1 * e);
      o('ctl', 'look', e);
    } },
    lookRight: { dur: 1.0, fn(p, o, c) {
      const e = c.keys(p, [[0, 0], [0.26, 1.05], [0.34, 1], [0.7, 1], [1, 0]]), lead = sst(0, 0.08, p) - sst(0.1, 0.3, p);
      o('head', 'ry', 0.75 * e); o('neck', 'ry', 0.25 * e); o('chest', 'ry', 0.08 * e); o('head', 'rz', -0.06 * e);
      gaze(o, 0.3 * lead, 0);
      o('earL', 'rx', -0.25 * e); o('earL', 'ry', 0.1 * e);
      o('ctl', 'look', e);
    } },
    rest: { dur: 5, fn(p, o, c) { /* a sigh to begin, then slower breathing, lids to 60 percent, the head 15 degrees lower and the neck 10, the ears relaxed, the tail still */
      const e = c.env(p, 0.25, 0.25);
      const inh = c.keys(p, [[0, 0], [0.1, 1], [0.22, -0.2], [0.35, 0], [1, 0]]);
      o('chest', 'sx', 0.025 * inh); o('body', 'sx', 0.015 * inh); o('neck', 'py', 0.008 * inh);
      o('ctl', 'lid', 0.6 * e); o('ctl', 'breath', -0.25 * e); o('ctl', 'amp', 0.5 * e);
      o('head', 'rx', 0.26 * e); o('neck', 'rx', 0.17 * e); o('head', 'py', -0.01 * e); o('chest', 'rx', 0.03 * e);
      o('earL', 'rz', -0.08 * e); o('earR', 'rz', 0.08 * e); o('earL', 'rx', 0.06 * e); o('earR', 'rx', 0.06 * e);
    } },
    dance: { dur: 2.3, fn(p, o, c) { /* the merry greeting (research 2.11): a play-bow with the tail up and wagging to its right, two bounces of the forefeet with a helicopter wag, a shake that flaps the ears, then it sits back, tilts its head and raises its brows, and settles */
      if (p >= 1) return;
      const t = p * 2.3;
      const B = c.keys(t, [[0, 0], [0.5, 1], [1.55, 1], [1.62, 0.92], [2.0, 0], [2.3, 0]]);
      const P = lerpP(REST, BOW, B);
      const hop = Math.max(0, Math.sin(TAU * 2.5 * (t - 0.5))) * c.bump(t, 0.45, 1.15);
      let legs = null;
      if (hop > 0) {
        legs = {};
        for (const L of ['L', 'R']) legs[L] = { toe: P.hind.toe, hock: P.hind.hock, wr: [P.fore.wr[0] + 0.03 * hop, P.fore.wr[1]], ftoe: [P.fore.toe[0] + 0.03 * hop, P.fore.toe[1] - 0.01 * hop] };
        if (P.cat) P.cat = [P.cat[0] + 0.04 * hop, P.cat[1]];
        P.by += 0.02 * hop;
      }
      trunk(o, P, 1, legs);
      o('body', 'py', -0.012 * c.bump(t, 1.98, 2.14));
      /* the head: low and turned 20 degrees to its right in the bow, up and tilted right afterwards, always on the reader */
      look(o, c.keys(t, [[0, 0], [0.3, 1], [2.1, 1], [2.3, 0]]));
      o('head', 'ry', -0.3 * B); o('head', 'rx', 0.12 * B);
      o('head', 'rz', 0.26 * c.keys(t, [[1.65, 0], [1.9, 1], [2.1, 1], [2.3, 0]]));
      ears(o, 0.3, c.keys(t, [[0, 0], [0.2, 1], [2.1, 1], [2.3, 0]]));
      brows(o, c.keys(t, [[0, 0], [0.3, 1], [1.0, 1], [1.2, 0], [1.8, 0], [2.0, 1], [2.2, 1], [2.3, 0]]));
      /* the tail: up and wagging 3.5 Hz to its right, the tip circling through the bounces, slower through the shake, 2.5 Hz as it sits */
      tailPose(o, TAIL_BOW, (i) => c.keys(t - i * 0.03, [[0, 0], [0.45, 1], [1.6, 1], [2.0, 0]]));
      tailPose(o, TAIL_HAPPY, (i) => c.keys(t, [[1.6, 0], [2.0, 0.5], [2.15, 0.4], [2.3, 0]]));
      const wz = c.keys(t, [[0, 0], [0.3, 1], [2.1, 1], [2.3, 0]]), hz = c.keys(t, [[0, 3.5], [1.1, 3.5], [1.6, 2.5], [2.3, 2.5]]);
      wag(o, t, hz, 0.55, 0.3, wz, c.bump(t, 0.45, 1.15));
      /* the shake: three cycles starting at the head, eyes shut for the middle one */
      shake(o, t, 1.1, 3, 0.48, c.bump(t, 1.06, 1.64));
      o('ctl', 'lid', c.bump(t, 1.26, 1.46));
    } },
  };
  K.finish(R);
  K.restTurn(R, 'head', [0, HEAD_YAW * 0.7, 0]);      /* bound straight, rests turned a little toward the reader: the neck bends into the turn */
  K.restTurn(R, 'neck', [0, HEAD_YAW * 0.3, 0]);
  return R;
}

export default {
  id: 'retriever',
  name: 'Golden retriever',
  latin: 'Canis familiaris',
  rests: 'floor',
  build: (THREE, kit) => buildRetriever(THREE, kit),
  update: (rig, dt, state) => rig.kit.update(rig, dt, state),
  play: (rig, clip, variant) => rig.kit.play(rig, clip, variant),
  rest: (rig) => rig.kit.rest(rig),
};
