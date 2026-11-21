/*
  The Civic Archive companion: the eastern gray squirrel (Sciurus carolinensis).

  Built on the companions' realism kit (kit.js). No usable model exists under the rules (research/squirrel.md, section 1:
  the archives hold only faceted toys), so the animal is sculpted in code from the research's proportions: head-body
  length (HB) is 0.78 units, the tail bone 0.89 HB with a plume as wide as the body, hind foot 0.24 HB, ear 0.115 HB,
  shoulder and hip 0.40 HB above the ground in the alert crouch, eyes large and lateral. The body, head, legs, ears and
  paws are one signed distance field surfaced as one mesh that bends over a skeleton of twenty bones (weights by distance
  to each bone, smoothed; a body bone never reaches the face, an ear bone only its ear); the tail is a second skinned mesh
  on a five-bone chain (a stiff root, three bending middle bones, a whipping tip, as Hofmann 2021 describes the three
  regions of a squirrel's tail). The coat is painted per vertex from the species sheet (grey agouti with the brown wash
  along the back and crown, a white belly and throat, tawny feet, pale ear backs, a buff eye ring) and dressed in short
  dense fur shells; the tail is painted in its hair-tip colours (silver, banded) and dressed in long thinning shells over
  a dark core, so it reads as a frosted plume. Wet black eyes with a glint; a glossy nose; dark claws; whiskers.

  Motion comes from the research: breathing at 1.1 Hz (alert) and 0.77 Hz (rest), blinks of 0.16 s, head saccades of
  0.12 s with holds, the tail on springs of about 3 Hz at the base with a damping ratio of a half (Fukushima 2021: a light,
  fast tail that follows and overshoots the body), half-bounds with the hind pair together and the forefeet staggered
  (Dunham 2019, Hildebrand 1977), the feet planted by two-bone IK while the body pitches nose-up 15 degrees on the push and
  nose-down 12 on the forelimb landing, tail flicks under 45 degrees and S-wave flags over it (McRae & Green 2014), the sit
  with the forepaws held to the chest and the head up (Makowska & Kramer 2007), the head-to-tail grooming chain (Kalueff
  2016), the fake burial (Steele 2008), the double hind-foot stamp, and the freeze-scan-bound stop-and-go.

  export default { id, name, latin, rests, build(THREE, kit) -> rig, update(rig, dt, state), play(rig, clip) -> seconds, rest(rig) }
    rig.root   1 unit = the body's height with the tail up, facing +z toward the reader, feet at y = 0
    rig.frame  the box, in root units, a camera should keep in view: { x: [min, max], y: [min, max] }
    clips      arrive, idleA, idleB (five fidgets), notice, react, talk, lookLeft, lookRight, rest, dance; every clip
               ends exactly on the rest pose.
*/

function buildSquirrel(THREE, K) {
  if (!K || !K.rig) throw new Error('the squirrel needs the companions kit: build(THREE, kit)');
  const { sd, surf, strip, circle, rgb, mixc, fbm, noise, sst, lerp, clamp, unit, PI, TAU } = K;
  const R = K.rig({
    id: 'squirrel', yaw: -0.85, frame: { x: [-0.34, 0.47], y: [-0.03, 0.98] }, fov: 34,
    breath: 1.1, blinkSpeed: 0.6, look: { yaw: 0.9, pitch: 0.45, snap: true },
    idles: ['idleA', 'idleB', 'idleB', 'idleB', 'lookLeft', 'lookRight', 'notice'],
  });
  const HEAD_YAW = 0.12;      /* the head rests turned a little toward the reader: the face shows three-quarters */
  const FACE = 0.55;          /* how much further the head turns to look at the reader, nose nearly on, one eye full on */

  /* colours from the species sheet (sRGB) */
  const GREY = rgb(0x8b8b87), GREY2 = rgb(0x67675f), PALE = rgb(0xbab9b3), DARK = rgb(0x48453f);
  const WASH = rgb(0x8c7658), WASH2 = rgb(0x9f8a6c), BELLY = rgb(0xf1eee8), BELLY2 = rgb(0xdedad0);
  const RING = rgb(0xd9ccb3), FOOT = rgb(0x9b7c5a), NOSE = rgb(0x2a221f), CLAW = rgb(0x2c2724), EARIN = rgb(0x5f5750);
  const TIP = rgb(0xd3d1cc), TIP2 = rgb(0xaeaca6), BAND = rgb(0x66635c), SILVER = rgb(0xe9e7e2);

  /* ---- the body on all fours: an alert crouch, the hindquarters high, the head raised ---- */
  const rump = sd.egg([0, 0.29, -0.215], [0.118, 0.128, 0.138]);
  const back = sd.egg([0, 0.315, -0.085], [0.106, 0.118, 0.15]);
  const chest = sd.egg([0, 0.295, 0.07], [0.096, 0.104, 0.112], [-0.2, 0, 0]);
  const neck = sd.limb([0, 0.335, 0.13], [0, 0.4, 0.2], 0.07, 0.06);
  const torsoF = sd.add(0.06, rump, back, chest, neck);
  const HC = [0, 0.42, 0.235];
  const skull = sd.egg(HC, [0.074, 0.07, 0.084]);
  /* a short, deep muzzle under a rounded brow: the eye sits nearer the nose than the ear, as on the real skull */
  const brow = sd.egg([0, 0.44, 0.282], [0.054, 0.044, 0.05]);
  const muzzle = sd.egg([0, 0.394, 0.30], [0.047, 0.042, 0.053]);
  const cheek = (s) => sd.egg([s * 0.047, 0.39, 0.265], [0.035, 0.034, 0.04]);
  const head0 = sd.add(0.03, skull, brow, muzzle, cheek(1), cheek(-1));
  /* the eyes sit high and to the sides (yaw 60 degrees off the nose), each on a slight bulge */
  const EYES = [];
  for (const s of [1, -1]) {
    const yaw = s * 0.98, pit = 0.12;
    const d = [Math.sin(yaw) * Math.cos(pit), Math.sin(pit), Math.cos(yaw) * Math.cos(pit)];
    EYES.push({ s, d, sp: K.hit(head0, HC, d) });
  }
  const bulge = (E) => sd.ball([E.sp[0] - E.d[0] * 0.014, E.sp[1] - E.d[1] * 0.014, E.sp[2] - E.d[2] * 0.014], 0.027);
  const headF = sd.add(0.02, head0, bulge(EYES[0]), bulge(EYES[1]));
  for (const E of EYES) E.sp = K.hit(headF, HC, E.d);
  /* ears: thin rounded leaves, cupped toward the front, tilted back and outward */
  const ear = (s) => {
    const F = sd.frame([s * 0.053, 0.508, 0.197], [-0.38, s * 0.3, s * 0.34]);
    const leaf = sd.egg([0, 0, 0], [0.025, 0.051, 0.013]);
    const cup = sd.egg([0, 0.008, 0.015], [0.017, 0.037, 0.011]);
    return { F, f: F.place(sd.sub(leaf, cup, 0.004)) };
  };
  const EaL = ear(1), EaR = ear(-1);
  const earReg = (s) => (x, y, z) => sst(0.452, 0.49, y) * sst(0.018, 0.045, s * x) * sst(0.13, 0.17, z) * sst(0.27, 0.235, z);
  /* legs, zigzag folded (Fischer 2002): shoulder-elbow-wrist-fingertips, hip-knee-heel-toes; the hind foot long and flat */
  const S = (s) => [s * 0.062, 0.33, 0.085], E = (s) => [s * 0.076, 0.215, 0.03], W = (s) => [s * 0.073, 0.085, 0.09], FT = (s) => [s * 0.073, 0.013, 0.168];
  const H = (s) => [s * 0.068, 0.30, -0.22], N = (s) => [s * 0.092, 0.20, -0.08], A = (s) => [s * 0.086, 0.045, -0.24], TO = (s) => [s * 0.09, 0.013, -0.045];
  const foreLeg = (s) => sd.add(0.018,
    sd.limb(S(s), E(s), 0.046, 0.033), sd.limb(E(s), W(s), 0.033, 0.024), sd.limb(W(s), FT(s), 0.022, 0.014),
    sd.egg([s * 0.073, 0.016, 0.135], [0.023, 0.012, 0.036]));
  const hindLeg = (s) => sd.add(0.025,
    sd.limb(H(s), N(s), 0.064, 0.043), sd.limb(N(s), A(s), 0.04, 0.028), sd.limb(A(s), TO(s), 0.027, 0.017),
    sd.egg([s * 0.089, 0.016, -0.14], [0.026, 0.013, 0.1]));
  const legsF = sd.add(0, foreLeg(1), foreLeg(-1), hindLeg(1), hindLeg(-1));
  const trunkF = sd.add(0.04, torsoF, headF);
  const bodyF = sd.add(0.035, trunkF, legsF, EaL.f, EaR.f);

  /* ---- the tail: a bone of 0.89 HB in an open S up behind and over the back, the plume as wide as the body seen from
     the side and little more than half that seen from behind (the hairs part along the spine and lie to the two sides),
     its outline only gently uneven: the softness comes from the long frosted shells ---- */
  const TP = [[0, 0.30, -0.31], [0, 0.355, -0.405], [0, 0.50, -0.44], [0, 0.655, -0.39], [0, 0.75, -0.27], [0, 0.765, -0.15], [0, 0.73, -0.07]];
  const TR = [0.042, 0.078, 0.104, 0.114, 0.106, 0.082, 0.034];
  const furry = (f, amp, fr) => { const g = (x, y, z) => f(x, y, z) + amp * (noise(x * fr, y * fr, z * fr) - 0.5); g.b = f.b ? [f.b[0], f.b[1], f.b[2], f.b[3] + amp] : null; return g; };
  /* the plume is a broad flat fan: wide seen from the side, thin seen from behind (the hairs part along the spine and
     lie to the two sides); its outline only gently uneven, the softness comes from the long shells */
  const tailF = furry(sd.xf(sd.chain(TP, TR, 0.04), [0, 0, 0], null, [0.62, 1, 1]), 0.006, 28);
  const SEGS = TP.slice(0, -1).map((P, i) => { const Q = TP[i + 1], dy = Q[1] - P[1], dz = Q[2] - P[2], l = Math.hypot(dy, dz); return { P, d: [dy / l, dz / l], l }; });
  const tailLen = SEGS.reduce((a, s) => a + s.l, 0);
  function tailParam(y, z) {      /* where a point sits along the tail (0 root, 1 tip) and the spine's direction there */
    let best = Infinity, t = 0, dir = [1, 0], acc = 0;
    for (const s of SEGS) {
      const u = clamp(((y - s.P[1]) * s.d[0] + (z - s.P[2]) * s.d[1]) / s.l, 0, 1);
      const dd = Math.hypot(y - (s.P[1] + s.d[0] * s.l * u), z - (s.P[2] + s.d[1] * s.l * u));
      if (dd < best) { best = dd; t = (acc + u * s.l) / tailLen; dir = s.d; }
      acc += s.l;
    }
    return { t, dir };
  }
  const noseF = sd.egg([0, 0.397, 0.355], [0.015, 0.012, 0.011]);
  const all = sd.min(bodyF, tailF, noseF);

  /* ---- painting the coat ---- */
  const isHead = (y, z) => y > 0.3 && z > 0.165 + 0.3 * (y - 0.36);
  const paintBody = (x, y, z, nx, ny, nz) => {
    const n = fbm(x * 52, y * 52, z * 52, 3), f = fbm(x * 130, y * 130, z * 130, 2), ax = Math.abs(x), s = x < 0 ? -1 : 1;
    const head = isHead(y, z), leg = legsF(x, y, z) < trunkF(x, y, z) - 0.004 && !head;
    const earness = Math.max(earReg(1)(x, y, z), earReg(-1)(x, y, z));
    const th = Math.atan2(ax, y - (head ? 0.405 : 0.30 + 0.03 * sst(-0.3, 0.1, z)));      /* 0 on top, PI/2 at the side, PI below */
    /* the grey agouti: salt and pepper, paler on the flanks */
    let c = mixc(GREY, GREY2, 0.6 * n);
    c = mixc(c, PALE, 0.42 * sst(0.5, 0.8, f));
    c = mixc(c, PALE, 0.22 * sst(0.9, 1.7, th));
    /* the brown wash along the back and over the crown, blotchy, a tinge rather than a coat */
    const washK = head ? 0.42 : 0.52 * (1 - 0.3 * sst(0.1, 0.25, z));
    c = mixc(c, mixc(WASH, WASH2, f), washK * sst(0.95, 0.2, th) * (0.55 + 0.45 * n));
    /* white underneath and up the lower flank; the throat and chin; the inner legs */
    let w = sst(1.85, 2.2, th + 0.15 * (n - 0.5));
    if (leg) w = Math.max(0.4 * sst(-0.2, -0.6, s * nx) * sst(0.08, 0.16, y), 0.3 * sst(-0.3, -0.7, ny) * sst(0.03, 0.09, y));      /* the paws themselves stay tawny */
    if (head) w = sst(2.05, 2.45, th + 0.1 * (n - 0.5)) * sst(0.31, 0.27, z) + 0.6 * sst(0.28, 0.35, z) * sst(0.395, 0.375, y) * sst(-0.1, -0.5, ny);
    c = mixc(c, mixc(BELLY, BELLY2, 0.3 + 0.5 * n), w);
    /* the legs and feet carry a tawny wash; the feet are rusty */
    if (leg) { c = mixc(c, WASH2, 0.3 * (1 - w)); c = mixc(c, FOOT, 0.65 * sst(0.1, 0.03, y) * (1 - 0.7 * w)); }
    /* the face: buff round the muzzle, a shade darker round the eyes */
    if (head) {
      c = mixc(c, mixc(WASH2, BELLY2, 0.55), 0.6 * sst(0.28, 0.335, z) * sst(0.44, 0.4, y));
      for (const Ey of EYES) c = mixc(c, DARK, 0.22 * sst(0.052, 0.03, Math.hypot(x - Ey.sp[0], y - Ey.sp[1], z - Ey.sp[2])));
      c = mixc(c, DARK, 0.5 * sst(0.006, 0.0, Math.abs(y - 0.362)) * sst(0.31, 0.33, z));      /* the mouth line */
    }
    /* ears: grey-brown, darker inside the cup, pale behind */
    if (earness > 0.05) {
      let e = mixc(mixc(GREY, WASH, 0.4), EARIN, 0.7 * sst(0.1, 0.6, nz));
      e = mixc(e, mixc(PALE, BELLY2, 0.5), 0.6 * sst(-0.1, -0.5, nz));
      c = mixc(c, e, earness);
    }
    return c;
  };
  const paintTail = (x, y, z, nx) => {
    const P = tailParam(y, z), n = fbm(x * 55, y * 55, z * 55, 2), f = fbm(x * 150, y * 150, z * 150, 2);
    let c = mixc(TIP, TIP2, 0.6 * n);
    const band = sst(0.3, 0.7, 0.5 + 0.5 * Math.sin(P.t * TAU * 6.5 + 2.5 * (noise(x * 14, y * 14, z * 14) - 0.5)));
    c = mixc(c, BAND, 0.22 * band);      /* the banding of the hairs shows through faintly, as on the real plume; never as rings */
    c = mixc(c, SILVER, 0.35 * sst(0.55, 0.85, f));
    c = mixc(c, SILVER, 0.65 * sst(0.6, 0.25, Math.abs(nx)));          /* the fringe, where the long hairs turn edge-on, is silver */
    c = mixc(c, mixc(WASH, TIP2, 0.5), 0.2 * sst(0.3, 0.0, P.t));     /* a brown tinge at the root */
    return c;
  };
  /* the groom: short dense fur combed back along the body and down the flanks, shortest on the face, hands and feet, none
     over the eye rings or the nose; the tail's long hairs lie back along it, longest in the middle of the plume */
  const groom = (x, y, z) => {
    const head = isHead(y, z);
    let len = head ? 0.42 + 0.25 * sst(0.3, 0.2, z) : 1;
    len *= 1 + 0.35 * sst(-0.15, -0.3, z) * sst(0.15, 0.25, y);
    len *= lerp(0.6, 1, sst(0.05, 0.14, y));
    for (const Ey of EYES) len *= sst(0.028, 0.05, Math.hypot(x - Ey.sp[0], y - Ey.sp[1], z - Ey.sp[2]));
    len *= sst(0.012, 0.03, Math.hypot(x, y - 0.397, z - 0.355));
    const earness = Math.max(earReg(1)(x, y, z), earReg(-1)(x, y, z));
    len *= 1 - 0.4 * earness;
    return [len, 1, -0.25 * Math.sign(x) * (head ? 0.3 : 1), -0.55, head ? -0.9 : -0.75];
  };
  const groomTail = (x, y, z) => {
    const P = tailParam(y, z);
    return [0.7 + 0.5 * Math.sin(PI * clamp(P.t, 0, 1)), 1, 0, P.dir[0], P.dir[1]];
  };

  /* materials */
  const furM = K.physical({ rough: 0.72, sheen: 0.5, sheenRough: 0.5, sheenColor: 0xd4d4d0, spec: 0.3, name: 'squirrel-fur' });
  const tailM = K.physical({ rough: 0.75, sheen: 0.7, sheenRough: 0.45, sheenColor: 0xe4e4e0, spec: 0.25, name: 'squirrel-tail' });
  const noseM = K.physical({ rough: 0.3, clearcoat: 0.8, ccRough: 0.15, spec: 0.7, name: 'squirrel-nose' });
  const clawM = K.physical({ rough: 0.4, clearcoat: 0.5, ccRough: 0.25, spec: 0.6, name: 'squirrel-claw' });
  const ringM = K.physical({ rough: 0.75, sheen: 0.35, spec: 0.3, name: 'squirrel-ring' });

  /* ---- joints: body (at the hips), chest, neck, head, ears; shoulder, elbow, wrist; hip, knee, heel; five tail bones ---- */
  K.joint(R, 'body', 'pose', [0, 0.30, -0.22]);
  K.joint(R, 'chest', 'body', [0, 0.32, -0.04]);
  K.joint(R, 'neck', 'chest', [0, 0.345, 0.135]);
  K.joint(R, 'head', 'neck', [0, 0.40, 0.205]);
  K.joint(R, 'earL', 'head', [0.05, 0.465, 0.205]);
  K.joint(R, 'earR', 'head', [-0.05, 0.465, 0.205]);
  for (const s of [1, -1]) {
    const n = s > 0 ? 'L' : 'R';
    K.joint(R, 'sh' + n, 'chest', S(s)); K.joint(R, 'el' + n, 'sh' + n, E(s)); K.joint(R, 'ha' + n, 'el' + n, W(s));
    K.joint(R, 'hip' + n, 'body', H(s)); K.joint(R, 'kn' + n, 'hip' + n, N(s)); K.joint(R, 'ft' + n, 'kn' + n, A(s));
  }
  K.joint(R, 'tail1', 'body', TP[0]); K.joint(R, 'tail2', 'tail1', TP[1]); K.joint(R, 'tail3', 'tail2', TP[2]);
  K.joint(R, 'tail4', 'tail3', TP[3]); K.joint(R, 'tail5', 'tail4', TP[4]);
  K.limit(R, 'head', { ry: [-1.5, 1.5], rx: [-0.9, 0.9], rz: [-0.5, 0.5] });
  K.limit(R, 'neck', { ry: [-0.9, 0.9], rx: [-0.7, 0.7] });

  /* ---- the skinned body ---- */
  const side = (s) => (x) => sst(0.005, 0.04, s * x);
  const bodyGeo = surf(bodyF, [-0.17, -0.005, -0.42, 0.17, 0.585, 0.41], 0.0105, paintBody, { ao: all, groom });
  const bones = [
    { j: 'body', a: [0, 0.29, -0.34], b: [0, 0.31, -0.07], r: 0.13 },
    { j: 'chest', a: [0, 0.31, -0.06], b: [0, 0.335, 0.125], r: 0.12, only: (x, y, z) => sst(0.21, 0.15, z) },
    { j: 'neck', a: [0, 0.34, 0.125], b: [0, 0.40, 0.195], r: 0.07, only: (x, y, z) => sst(0.27, 0.21, z) },
    { j: 'head', a: [0, 0.415, 0.205], b: [0, 0.40, 0.36], r: 0.11, only: (x, y, z) => sst(0.14, 0.2, z) * (1 - 0.9 * Math.max(earReg(1)(x, y, z), earReg(-1)(x, y, z))) },
    { j: 'earL', a: [0.05, 0.47, 0.205], b: [0.064, 0.56, 0.18], r: 0.03, only: earReg(1) },
    { j: 'earR', a: [-0.05, 0.47, 0.205], b: [-0.064, 0.56, 0.18], r: 0.03, only: earReg(-1) },
  ];
  for (const s of [1, -1]) {
    const n = s > 0 ? 'L' : 'R';
    bones.push({ j: 'sh' + n, a: S(s), b: E(s), r: 0.046, only: side(s) }, { j: 'el' + n, a: E(s), b: W(s), r: 0.034 }, { j: 'ha' + n, a: W(s), b: FT(s), r: 0.03 },
      { j: 'hip' + n, a: H(s), b: N(s), r: 0.06, only: side(s) }, { j: 'kn' + n, a: N(s), b: A(s), r: 0.04 }, { j: 'ft' + n, a: A(s), b: TO(s), r: 0.035 });
  }
  const bodyMesh = K.skin(R, bodyGeo, bones, furM, { smooth: 3, name: 'squirrel-body' });
  K.fur(R, bodyMesh, { len: 0.013, dens: 150, thin: 0.82, root: 0.7, clump: 0.28, comb: 0.85, droop: 0.07, min: 0.45, max: 8 });

  /* ---- the skinned tail ---- */
  const tailGeo = surf(tailF, [-0.13, 0.16, -0.6, 0.13, 0.93, 0.02], 0.012, paintTail, { ao: all, groom: groomTail });
  const tailMesh = K.skin(R, tailGeo, [
    { j: 'tail1', a: TP[0], b: TP[1], r: 0.09 }, { j: 'tail2', a: TP[1], b: TP[2], r: 0.1 }, { j: 'tail3', a: TP[2], b: TP[3], r: 0.1 },
    { j: 'tail4', a: TP[3], b: TP[4], r: 0.1 }, { j: 'tail5', a: TP[4], b: TP[6], r: 0.09 },
  ], tailM, { smooth: 3, name: 'squirrel-tail' });
  K.fur(R, tailMesh, { len: 0.058, dens: 105, thin: 0.85, root: 0.5, clump: 0.1, comb: 0.6, droop: 0.1, min: 0.5, max: 14 });
  /* on the lean tier there are no shells, so the dark roots that the hairs would cover are lightened */
  const roots = (t) => { tailM.userData.u.uRootDark.value = t === 0 ? 0.9 : 0.52; furM.userData.u.uRootDark.value = t === 0 ? 0.94 : 0.7; };
  roots(K.tier);
  const offTier = K.onTier(roots);
  const dispose0 = R.dispose; R.dispose = () => { offTier(); dispose0(); };

  /* the nose, rigid on the head */
  K.put(R, 'head', surf(noseF, [-0.025, 0.375, 0.332, 0.025, 0.42, 0.378], 0.0028, () => NOSE, { ao: all }), noseM);
  /* claws: four on each paw, on the hand and foot bones */
  const claws = (base, s) => sd.add(0, ...[-0.013, -0.0045, 0.0045, 0.013].map((dx) =>
    sd.limb([base[0] + dx, base[1], base[2]], [base[0] + dx * 1.35, base[1] - 0.005, base[2] + 0.02], 0.0036, 0.0012)));
  for (const s of [1, -1]) {
    const n = s > 0 ? 'L' : 'R', fb = [s * 0.073, 0.009, 0.17], hb = [s * 0.09, 0.009, -0.04];
    K.put(R, 'ha' + n, surf(claws(fb, s), [fb[0] - 0.03, -0.005, fb[2] - 0.01, fb[0] + 0.03, 0.025, fb[2] + 0.035], 0.0026, () => CLAW), clawM);
    K.put(R, 'ft' + n, surf(claws(hb, s), [hb[0] - 0.03, -0.005, hb[2] - 0.01, hb[0] + 0.03, 0.025, hb[2] + 0.035], 0.0026, () => CLAW), clawM);
  }
  /* whiskers: five a side, long (0.15 HB), swept back and a little down, drawn as fine pale lines */
  {
    const P = [], hp = R.piv.head;
    for (const s of [1, -1]) for (let i = 0; i < 5; i++) {
      const k = i - 2, b = [s * 0.037, 0.389 + 0.0045 * k, 0.316 - 0.004 * Math.abs(k)];
      const d = unit([s * 0.8, 0.12 + 0.17 * k, -0.42 + 0.12 * Math.abs(k)]), L = 0.12 + 0.012 * (2 - Math.abs(k));
      const p1 = [b[0] + d[0] * L * 0.5, b[1] + d[1] * L * 0.5 + 0.006, b[2] + d[2] * L * 0.5], p2 = [b[0] + d[0] * L, b[1] + d[1] * L + 0.004, b[2] + d[2] * L - 0.012];
      P.push(b[0] - hp[0], b[1] - hp[1], b[2] - hp[2], p1[0] - hp[0], p1[1] - hp[1], p1[2] - hp[2], p1[0] - hp[0], p1[1] - hp[1], p1[2] - hp[2], p2[0] - hp[0], p2[1] - hp[1], p2[2] - hp[2]);
    }
    const g = new THREE.BufferGeometry(); g.setAttribute('position', new THREE.Float32BufferAttribute(P, 3));
    const m = new THREE.LineBasicMaterial({ color: 0xe9e5dd, transparent: true, opacity: 0.55, depthWrite: false });
    const w = new THREE.LineSegments(g, m); w.name = 'whiskers'; w.frustumCulled = false; w.renderOrder = 6;
    R.j.head.add(w); R.geos.push(g); R.mats.add(m);
  }
  /* eyes: large, black, wet, each in a buff ring; the lids are grey-brown */
  for (const Ey of EYES) {
    const { s, d, sp } = Ey, r = 0.02, c = [sp[0] - d[0] * r * 0.55, sp[1] - d[1] * r * 0.55, sp[2] - d[2] * r * 0.55];
    const name = s > 0 ? 'eyeL' : 'eyeR';
    /* the lids are furred, so a shut eye is a grey-brown dome in the face and a blink can be seen; the ring of buff fur
       round the eye is thin and only a shade paler than the cheek, never a white that would read as an eye's white */
    K.eye(R, name, 'head', c, d, r, { iris: 0x1a120c, iris2: 0x3a2516, pupil: 0.62, irisAngle: 1.0, sclera: 0x1a1512, limbal: 0x0a0806,
      lid: mixc(GREY2, DARK, 0.35), lidMat: { rough: 0.85, sheen: 0.2, spec: 0.3, name: name + '-lid' }, open: -0.75, shut: 1.5, glint: 0.26, lowerShare: 0.3, gloss: 0.8, wet: 0.5 });      /* a glint this size stays under a shut lid */
    K.put(R, 'head', strip(headF, circle(sp, d, 0.0225, 44), 0.0065, RING, { closed: true, lift: 0.0018 }), ringM);
  }

  /* ---- secondary motion: the tail follows the body with a lag and an overshoot, 3 Hz and a damping ratio of a half
     at the base, lighter and freer toward the tip; the ears flick after a head turn ---- */
  K.spring(R, 'tail2', { ch: 'rx', k: 330, c: 18, gain: 0.035, dir: [0, 1, -0.25], lim: [-0.45, 0.45] });
  K.spring(R, 'tail3', { ch: 'rx', k: 250, c: 15, gain: 0.055, dir: [0, 1, 0.3], lim: [-0.6, 0.6] });
  K.spring(R, 'tail4', { ch: 'rx', k: 180, c: 12, gain: 0.08, dir: [0, 0.6, 0.8], lim: [-0.75, 0.75] });
  K.spring(R, 'tail5', { ch: 'rx', k: 150, c: 9, gain: 0.11, dir: [0, 0.1, 1], lim: [-0.9, 0.9] });
  K.spring(R, 'tail3', { ch: 'rz', k: 200, c: 13, gain: 0.045, dir: [0, 1, 0.3], lim: [-0.5, 0.5] });
  K.spring(R, 'tail5', { ch: 'rz', k: 130, c: 8.5, gain: 0.08, dir: [0, 0.1, 1], lim: [-0.7, 0.7] });
  K.spring(R, 'earL', { ch: 'rz', k: 280, c: 14, gain: 0.015, dir: [0.15, 1, -0.2], lim: [-0.3, 0.3] });
  K.spring(R, 'earR', { ch: 'rz', k: 280, c: 14, gain: 0.015, dir: [-0.15, 1, -0.2], lim: [-0.3, 0.3] });

  /* ---- legs: two-bone IK keeps the paws where they stand while the body pitches, drops, rises or sits up ---- */
  const dist = (a, b) => Math.hypot(a[0] - b[0], a[1] - b[1], a[2] - b[2]);
  const L1h = dist(H(1), N(1)), L2h = dist(N(1), A(1)), L1f = dist(S(1), E(1)), L2f = dist(E(1), W(1));
  const hz0 = A(1)[2] - H(1)[2], hy0 = A(1)[1] - H(1)[1], fz0 = W(1)[2] - S(1)[2], fy0 = W(1)[1] - S(1)[1];
  const [hh0, hk0] = K.ik2(L1h, L2h, hz0, hy0, 1), [fh0, fk0] = K.ik2(L1f, L2f, fz0, fy0, -1);
  const BP = [0.30, -0.22], CP = [0.32, -0.04], SH = [0.33, 0.085];      /* body pivot, chest pivot, shoulder: (y, z) */
  const rotYZ = (y, z, th) => [y * Math.cos(th) - z * Math.sin(th), y * Math.sin(th) + z * Math.cos(th)];
  /* P: beta the body's pitch (nose down positive), gamma the chest's own pitch, lift the body's rise; hind and fore:
     [[forward offset, lift] left, [..] right] for planted paws (null leaves the arms to the clip); free 0..1 blends the
     arms toward the clip's own pose; toes curls the paw while it is lifted */
  function limbs(o, P) {
    const beta = P.beta || 0, gamma = P.gamma || 0, lift = P.lift || 0, free = P.free || 0;
    for (let i = 0; i < 2; i++) {
      const nm = i ? 'R' : 'L';
      if (P.hind) {
        const [off, fl] = P.hind[i];
        const [y2, z2] = rotYZ(hy0 + fl - lift, hz0 + off, -beta);
        const [h, k] = K.ik2(L1h, L2h, z2, y2, 1), dh = -(h - hh0), dk = -(k - hk0);
        o('hip' + nm, 'rx', dh); o('kn' + nm, 'rx', dk); o('ft' + nm, 'rx', -(beta + dh + dk) + (P.toes || 0) * fl);
      }
      if (P.fore && free < 1) {
        const [off, fl] = P.fore[i], cb = Math.cos(beta), sb = Math.sin(beta), cg = Math.cos(beta + gamma), sg = Math.sin(beta + gamma);
        const cpy = BP[0] + (CP[0] - BP[0]) * cb - (CP[1] - BP[1]) * sb, cpz = BP[1] + (CP[0] - BP[0]) * sb + (CP[1] - BP[1]) * cb;
        const shy = cpy + (SH[0] - CP[0]) * cg - (SH[1] - CP[1]) * sg, shz = cpz + (SH[0] - CP[0]) * sg + (SH[1] - CP[1]) * cg;
        const [y2, z2] = rotYZ(SH[0] + fy0 + fl - (shy + lift), SH[1] + fz0 + off - shz, -(beta + gamma));
        const [h, k] = K.ik2(L1f, L2f, z2, y2, -1), dh = -(h - fh0) * (1 - free), dk = -(k - fk0) * (1 - free);
        o('sh' + nm, 'rx', dh); o('el' + nm, 'rx', dk); o('ha' + nm, 'rx', -((beta + gamma) * (1 - free) + dh + dk) + (P.toes || 0) * fl);
      }
    }
  }
  /* the arms held free of the ground: a pose (shoulder, elbow, wrist pitch; wrist roll) scaled by a weight */
  const arms = (o, w, sh, el, ha, roll) => {
    o('shL', 'rx', sh * w); o('shR', 'rx', sh * w); o('elL', 'rx', el * w); o('elR', 'rx', el * w);
    o('haL', 'rx', ha * w); o('haR', 'rx', ha * w); o('haL', 'rz', (roll || 0) * w); o('haR', 'rz', -(roll || 0) * w);
  };
  /* sitting up on the haunches: the body pitches 57 degrees about the hips and settles down 0.09, the hind legs fold to
     keep the feet, the forepaws come to the chest, the head stays level, the tail stands up behind and curls tighter */
  function sit(o, up, pose) {
    const beta = -1.0 * up, lift = -0.09 * up, A = pose || {};
    o('body', 'rx', beta); o('body', 'py', lift);
    limbs(o, { beta, lift, hind: [[0, 0], [0, 0]] });
    arms(o, up, A.sh == null ? -1.45 : A.sh, A.el == null ? -1.35 : A.el, A.ha == null ? -0.35 : A.ha, A.roll == null ? 0.5 : A.roll);
    o('neck', 'rx', 0.35 * up); o('head', 'rx', 0.55 * up);
    o('tail1', 'rx', 0.75 * up); o('tail3', 'rx', 0.22 * up); o('tail4', 'rx', 0.18 * up);
    return { beta, lift };
  }
  /* a wave running from the base of the tail to the tip (a flag), with a sideways S; amp 0.5 gives the tip 75 degrees */
  const flag = (o, p, hz, amp, ph) => {
    const w = TAU * hz * p + (ph || 0);
    o('tail1', 'rx', 0.3 * amp * Math.sin(w)); o('tail2', 'rx', 0.5 * amp * Math.sin(w - 0.7)); o('tail3', 'rx', 0.6 * amp * Math.sin(w - 1.4));
    o('tail4', 'rx', 0.6 * amp * Math.sin(w - 2.1)); o('tail5', 'rx', 0.6 * amp * Math.sin(w - 2.8));
    o('tail3', 'rz', 0.2 * amp * Math.sin(w - 1.0)); o('tail5', 'rz', 0.3 * amp * Math.sin(w - 2.4));
  };
  /* a flick: the tip whips up and back in a fifth of a second, the middle following */
  const flick = (o, c, p, a, amp) => {
    const b = a + 0.06, d = b + 0.06;
    o('tail5', 'rx', amp * (c.bump(p, a, b) - 0.45 * c.bump(p, b, d))); o('tail4', 'rx', 0.5 * amp * c.bump(p, a + 0.015, b + 0.015)); o('tail3', 'rz', 0.25 * amp * c.bump(p, a, d));
  };
  const ears = (o, rx, rz) => { o('earL', 'rx', rx); o('earR', 'rx', rx); if (rz) { o('earL', 'rz', -rz); o('earR', 'rz', rz); } };
  const headTo = (o, yaw, e, roll) => { o('neck', 'ry', 0.3 * yaw * e); o('head', 'ry', 0.7 * yaw * e); o('head', 'rz', (roll == null ? -0.3 : roll) * yaw * e); o('earL', 'ry', -0.15 * yaw * e); o('earR', 'ry', -0.15 * yaw * e); };

  /* ---- breathing, attention, ducking ---- */
  R.spec.life = (o, L) => {
    const b = L.b;
    o('chest', 'sx', 0.02 * b); o('chest', 'sz', 0.014 * b); o('body', 'sx', 0.012 * b); o('body', 'sy', 0.007 * b);
    o('head', 'py', 0.002 * b);
    const yaw = L.yaw > 0 ? L.yaw : 0.55 * L.yaw;      /* the body already faces left, so a look that way is a smaller turn */
    o('neck', 'ry', 0.35 * yaw); o('head', 'ry', 0.65 * yaw); o('head', 'rz', -0.22 * yaw);
    o('head', 'rx', 0.75 * L.pitch); o('neck', 'rx', 0.25 * L.pitch);
    o('earL', 'ry', -0.15 * yaw); o('earR', 'ry', -0.15 * yaw);
    if (!L.still) { o('tail5', 'rx', 0.04 * Math.sin(L.t * 1.9)); o('tail4', 'rz', 0.025 * Math.sin(L.t * 1.3 + 1)); }
  };
  R.spec.duck = (o, d) => {      /* flattens like a squirrel pressed to the bark, and slides toward the edge */
    o('mover', 'px', 0.32 * d); o('body', 'py', -0.045 * d); o('chest', 'rx', 0.12 * d);
    limbs(o, { gamma: 0.12 * d, lift: -0.045 * d, hind: [[0, 0], [0, 0]], fore: [[0, 0], [0, 0]] });
    o('head', 'rx', 0.3 * d); o('head', 'py', -0.02 * d); ears(o, -0.2 * d, 0.3 * d);
    o('tail3', 'rx', 0.2 * d); o('tail4', 'rx', 0.25 * d);
  };

  /* ---- the arrival: three half-bounds in from the right, shortening as it slows (the hind pair together, the forefeet
     0.02 s apart; two flights a stride, the body pitching nose-up on the push and nose-down onto the hands; the tail
     streams in the long flight and curls in the gathered one), a landing that settles with weight while the body turns
     to its resting angle, a tail flick, and a head snap to the reader ---- */
  const DD = (p) => { const u = Math.min(1, p / 0.72); return 1.3 * Math.pow(1 - u, 1.6); };      /* distance still to go */
  const ST = 0.2;      /* one stride of the clip's 1.5 s: 0.30 s */
  const strideLen = (k) => DD(k * ST) - DD((k + 1) * ST);
  const hindAt = (p, c) => {      /* [forward offset of the hind feet, their lift] */
    p = Math.max(0, p);
    const i = Math.min(2, Math.floor(p / ST)), phi = p / ST - i, p0 = i * ST;
    const reach = (k) => (k >= 3 ? DD(3 * ST) : 0.07 + 0.12 * strideLen(k));
    if (p >= 3 * ST) return [reach(3) + DD(p) - DD(3 * ST), 0];
    if (phi < 0.42) return [reach(i) + DD(p) - DD(p0), 0];
    const u = (phi - 0.42) / 0.58, a = reach(i) + DD(p0 + 0.42 * ST) - DD(p0);
    return [c.lerp(a, reach(i + 1), u * u * (3 - 2 * u)), 0.05 * (strideLen(i) / 0.5) * Math.sin(PI * u)];
  };
  const foreAt = (pp, c) => {
    const j = Math.min(2, Math.floor(Math.max(0, pp) / ST)), ph = pp / ST - j;
    const reach = (k) => (k >= 2 ? DD(2.55 * ST) : 0.05 + 0.1 * strideLen(k)), land = (k) => (k + 0.55) * ST;
    if (pp >= land(2)) return [reach(2) + DD(pp) - DD(land(2)), 0];
    if (ph >= 0.55 && ph < 0.8) return [reach(j) + DD(pp) - DD(land(j)), 0];
    const k = ph >= 0.8 ? j : j - 1;
    const a = k < 0 ? -0.06 : reach(k) + DD((k + 0.8) * ST) - DD(land(k)), pa = k < 0 ? -0.2 * ST : (k + 0.8) * ST;
    const u = c.clamp((pp - pa) / (land(k + 1) - pa), 0, 1);
    return [c.lerp(a, reach(k + 1), u * u * (3 - 2 * u)), 0.04 * Math.sin(PI * u) * (strideLen(Math.max(0, k)) / 0.5)];
  };
  R.clips = {
    arrive: { dur: 1.5, fn(p, o, c) {
      o('mover', 'px', DD(p));
      o('pose', 'ry', -0.72 * (1 - c.ramp(p, 0.6, 0.86)));      /* faces the way it runs, then turns to its resting angle */
      let lift, beta, gamma, stream = 0, gather = 0;
      if (p < 3 * ST) {
        const i = Math.floor(p / ST), phi = p / ST - i, sc = strideLen(i) / 0.5;
        lift = sc * (0.05 * c.hop(phi, 0.42, 0.56) + 0.04 * c.hop(phi, 0.8, 1.0)) - 0.012 * sc * c.bump(phi, 0, 0.14);
        beta = Math.sqrt(sc) * c.keys(phi, [[0, -0.05], [0.4, -0.26], [0.7, 0.21], [1, -0.05]]);
        gamma = sc * c.keys(phi, [[0, 0.12], [0.45, -0.15], [0.9, 0.32], [1, 0.12]]);
        stream = sc * c.hop(phi, 0.38, 0.62); gather = sc * c.hop(phi, 0.78, 1.0);
      } else {
        const sc = strideLen(2) / 0.5;
        lift = c.keys(p, [[0.6, 0], [0.65, -0.03], [0.73, 0.008], [0.8, -0.002], [0.88, 0]]);
        beta = c.keys(p, [[0.6, -0.05 * Math.sqrt(sc)], [0.68, 0.1], [0.78, -0.03], [0.88, 0]]);
        gamma = c.keys(p, [[0.6, 0.12 * sc], [0.7, 0.25], [0.8, -0.04], [0.9, 0]]);
      }
      o('mover', 'py', lift); o('body', 'rx', beta); o('chest', 'rx', gamma);
      const hl = hindAt(p, c), hr = hindAt(p - 0.01 * ST, c), fl = foreAt(p, c), fr = foreAt(p - 0.07 * ST, c);
      limbs(o, { beta, gamma, lift, hind: [hl, hr], fore: [fl, fr], toes: 3 });
      o('neck', 'rx', -0.3 * beta); o('head', 'rx', -0.5 * beta);      /* the head stays the steady point */
      o('tail2', 'rx', -0.25 * stream + 0.1 * gather); o('tail3', 'rx', -0.45 * stream + 0.25 * gather);
      o('tail4', 'rx', -0.55 * stream + 0.3 * gather); o('tail5', 'rx', -0.5 * stream + 0.2 * gather);
      ears(o, -0.2 * (stream + gather), 0);
      flick(o, c, p, 0.69, 0.5);
      const snap = c.keys(p, [[0.72, 0], [0.8, 1.08], [0.86, 1], [0.94, 1], [1, 0]]);
      headTo(o, FACE, snap); ears(o, 0.25 * snap, 0);
      o('ctl', 'look', 1 - c.ramp(p, 0.9, 1));
    } },
    idleA: { dur: 4.5, fn(p, o, c) { /* breathing a little deeper, the tail tip stirring, one small head saccade and hold */
      o('ctl', 'amp', 0.45 * c.env(p, 0.2, 0.3));
      const e = c.env(p, 0.15, 0.2);
      o('tail5', 'rx', 0.09 * Math.sin(TAU * 1.35 * p) * e); o('tail4', 'rz', 0.04 * Math.sin(TAU * 0.9 * p + 1) * e);
      o('body', 'rz', 0.02 * Math.sin(TAU * p) * e);
      const k = c.keys(p, [[0.27, 0], [0.3, 0.42], [0.62, 0.42], [0.66, 0], [1, 0]]);
      headTo(o, 1, k);
      o('ctl', 'look', c.bump(p, 0.24, 0.7));
    } },
    idleB: { variants: 5, dur: (v) => [2.0, 2.4, 3.2, 3.6, 3.0][v], fn(p, o, c) {
      if (c.v === 0) { /* a tail flag bout: three S-waves base to tip at 2 Hz, braced, eyes on the reader */
        const e = c.bump(p, 0.04, 0.96);
        flag(o, p, 4, 0.5 * e);
        o('chest', 'rx', 0.06 * e); limbs(o, { gamma: 0.06 * e, hind: [[0, 0], [0, 0]], fore: [[0, 0], [0, 0]] });
        headTo(o, 0.5 * FACE, c.env(p, 0.1, 0.2)); ears(o, 0.25 * e, 0);
        o('ctl', 'look', 0.6 * c.env(p, 0.1, 0.2));
      } else if (c.v === 1) { /* freeze and scan: dead still, quick shallow breaths, two head snaps with holds, then on */
        const e = c.env(p, 0.06, 0.1);
        o('ctl', 'amp', -0.35 * e); o('ctl', 'breath', 0.4 * e);
        const lift = -0.012 * e;
        o('body', 'py', lift); limbs(o, { lift, hind: [[0, 0], [0, 0]], fore: [[0, 0], [0, 0]] });
        const k = c.keys(p, [[0.08, 0], [0.13, -0.78], [0.42, -0.78], [0.47, 0.62], [0.78, 0.62], [0.84, 0], [1, 0]]);
        headTo(o, 1, k, -0.25);
        o('head', 'rx', -0.08 * e); ears(o, 0.2 * e, 0);
        o('ctl', 'look', e);
      } else if (c.v === 2) { /* the face wash: sits up, six quick strokes of both paws, two slow ones a side, a shake */
        const up = c.keys(p, [[0, 0], [0.1, 1.04], [0.14, 1], [0.84, 1], [0.95, -0.03], [1, 0]]);
        sit(o, up, { sh: -1.6, el: -1.5, ha: -0.5, roll: 0.3 });
        const w1 = c.bump(p, 0.1, 0.6), st = Math.sin(TAU * 6 * (p - 0.12) / 0.47);
        arms(o, w1, 0.12 * Math.cos(TAU * 6 * (p - 0.12) / 0.47), 0.35 * st, 0.2 * st, 0);
        o('head', 'rx', 0.45 * c.bump(p, 0.08, 0.84) + 0.05 * st * w1);
        o('shL', 'rx', -0.3 * c.bump(p, 0.6, 0.69)); o('elL', 'rx', 0.3 * c.bump(p, 0.6, 0.69)); o('head', 'rz', -0.2 * c.bump(p, 0.6, 0.69));
        o('shR', 'rx', -0.3 * c.bump(p, 0.69, 0.78)); o('elR', 'rx', 0.3 * c.bump(p, 0.69, 0.78)); o('head', 'rz', 0.2 * c.bump(p, 0.69, 0.78));
        const sh = c.bump(p, 0.78, 0.87) * Math.sin(TAU * 10 * p);
        o('body', 'rz', 0.07 * sh); o('head', 'rz', 0.12 * sh); o('tail3', 'rz', 0.15 * sh);
        o('ctl', 'look', Math.min(1, up * 1.5));
      } else if (c.v === 3) { /* handling a nut: sits up, turns it in the forepaws with alternate pushes, gnaws, scans */
        const up = c.keys(p, [[0, 0], [0.09, 1.05], [0.13, 1], [0.86, 1], [0.96, -0.03], [1, 0]]);
        sit(o, up, { sh: -1.3, el: -1.55, ha: -0.4, roll: 0.55 });
        const e = c.bump(p, 0.1, 0.9), turn = Math.sin(TAU * 1.4 * p);
        o('elL', 'rx', 0.14 * turn * e); o('elR', 'rx', -0.14 * turn * e); o('haL', 'rz', 0.25 * turn * e); o('haR', 'rz', 0.25 * turn * e);
        const gnaw = (c.bump(p, 0.15, 0.35) + c.bump(p, 0.5, 0.72)) * Math.sin(TAU * 14 * p);
        o('head', 'rx', 0.03 * gnaw + 0.08 * e);
        const k = c.keys(p, [[0.36, 0], [0.4, 0.55], [0.48, 0.55], [0.52, 0], [0.74, 0], [0.78, -0.5], [0.86, -0.5], [0.9, 0], [1, 0]]);
        headTo(o, 1, k);
        o('tail5', 'rx', 0.06 * Math.sin(TAU * 7 * p) * e);
        o('ctl', 'look', Math.min(1, up * 1.5));
      } else { /* a fake burial: head down, three digging strokes, a press with the nose, two pats, a look up */
        const e = c.env(p, 0.08, 0.12), low = c.keys(p, [[0, 0], [0.1, 1], [0.72, 1], [0.86, 0], [1, 0]]);
        const lift = -0.02 * low, gamma = 0.22 * low;
        o('body', 'py', lift); o('chest', 'rx', gamma);
        limbs(o, { gamma, lift, hind: [[0, 0], [0, 0]], fore: [[0, 0], [0, 0]], free: low });
        o('neck', 'rx', 0.3 * low); o('head', 'rx', 0.5 * low + 0.3 * c.bump(p, 0.45, 0.56));
        const dig = c.bump(p, 0.1, 0.45), w = TAU * 3 * (p - 0.1) / 0.35 * 1.0;
        o('shL', 'rx', (-0.55 + 0.45 * Math.sin(w)) * dig * low); o('shR', 'rx', (-0.55 - 0.45 * Math.sin(w)) * dig * low);
        o('elL', 'rx', (-0.4 + 0.35 * Math.cos(w)) * dig * low); o('elR', 'rx', (-0.4 - 0.35 * Math.cos(w)) * dig * low);
        const pat = c.bump(p, 0.58, 0.72), pw = Math.sin(TAU * 2 * (p - 0.58) / 0.14);
        arms(o, pat * low, -0.5 + 0.3 * pw, -0.3 - 0.3 * pw, -0.2, 0);
        arms(o, low * (1 - dig) * (1 - pat), -0.35, -0.2, -0.1, 0);
        const up = c.keys(p, [[0.74, 0], [0.8, 1], [0.9, 1], [0.96, 0], [1, 0]]);
        headTo(o, 0.9 * FACE, up); o('head', 'rx', -0.35 * up); ears(o, 0.25 * up, 0);
        o('tail4', 'rx', 0.15 * low); o('tail5', 'rx', 0.2 * low);
        o('ctl', 'look', e);
      }
    } },
    notice: { dur: 1.2, fn(p, o, c) { /* the head snaps to the reader in 0.12 s and holds, ears forward; a tail-tip flick */
      const e = c.keys(p, [[0, 0], [0.1, 1.1], [0.16, 1], [0.78, 1], [0.9, 0], [1, 0]]);
      headTo(o, FACE, e); o('head', 'rx', -0.06 * e); ears(o, 0.25 * e, 0);
      flick(o, c, p, 0.2, 0.55);
      o('ctl', 'look', c.env(p, 0.06, 0.12));
    } },
    react: { dur: 1.6, fn(p, o, c) { /* sits up tall, forepaws to the chest, the tail curls tighter and fluffs, one flag wave, down with weight */
      const up = c.keys(p, [[0, 0], [0.17, 1.06], [0.25, 1], [0.7, 1], [0.86, -0.04], [1, 0]]);
      sit(o, up);
      headTo(o, FACE, up, -0.25); o('head', 'rx', -0.05 * up); ears(o, 0.25 * up, 0);
      const fl = c.bump(p, 0.22, 0.62);
      flag(o, p, 2.5, 0.45 * fl, -TAU * 2.5 * 0.22);
      o('tail2', 's', 0.1 * up); o('tail3', 's', 0.08 * up);
      o('ctl', 'look', Math.min(1, up * 1.5));
    } },
    talk: { dur: 3, fn(p, o, c) { /* attentive: the forequarters rise, the face comes to the reader, small nods, the tail tip quivers */
      const e = c.env(p, 0.12, 0.2), gamma = -0.2 * e;
      o('chest', 'rx', gamma); limbs(o, { gamma, hind: [[0, 0], [0, 0]], fore: [[0, 0], [0, 0]] });
      headTo(o, FACE, e, -0.2);
      o('head', 'rx', 0.07 * Math.sin(TAU * 4.5 * p) * e + 0.1 * e); o('head', 'rz', 0.08 * Math.sin(TAU * p) * e);
      ears(o, 0.25 * e, 0);
      o('tail5', 'rx', 0.06 * Math.sin(TAU * 9 * p) * e); o('tail4', 'rx', 0.08 * Math.sin(TAU * 2 * p) * e);
      o('ctl', 'look', 0.7 * e);
    } },
    lookLeft: { dur: 1.0, fn(p, o, c) { /* a quick turn further left, a hold with the eyes drifting against the head, back */
      const e = c.keys(p, [[0, 0], [0.1, 1.06], [0.15, 1], [0.76, 1], [0.86, 0], [1, 0]]);
      headTo(o, -0.55, e, -0.2);
      const drift = c.keys(p, [[0.15, 0], [0.5, 1], [0.76, 1], [0.86, 0], [1, 0]]);
      o('eyeL', 'ry', 0.1 * drift); o('eyeR', 'ry', 0.1 * drift);
      o('ctl', 'look', c.env(p, 0.06, 0.12));
    } },
    lookRight: { dur: 1.0, fn(p, o, c) { /* a big turn toward the reader's right, past the camera */
      const e = c.keys(p, [[0, 0], [0.1, 1.06], [0.15, 1], [0.76, 1], [0.86, 0], [1, 0]]);
      headTo(o, 1.35, e, -0.22);
      const drift = c.keys(p, [[0.15, 0], [0.5, 1], [0.76, 1], [0.86, 0], [1, 0]]);
      o('eyeL', 'ry', -0.1 * drift); o('eyeR', 'ry', -0.1 * drift);
      o('ctl', 'look', c.env(p, 0.06, 0.12));
    } },
    rest: { dur: 5, fn(p, o, c) { /* a lower crouch, the tail laid forward along the back like a blanket, lids half down, slower breath */
      const e = c.env(p, 0.25, 0.25), lift = -0.04 * e, gamma = 0.08 * e;
      o('body', 'py', lift); o('chest', 'rx', gamma);
      limbs(o, { gamma, lift, hind: [[0, 0], [0, 0]], fore: [[0, 0], [0, 0]] });
      o('neck', 'rx', 0.12 * e); o('head', 'rx', 0.2 * e); o('head', 'py', -0.015 * e);
      o('tail2', 'rx', 0.1 * e); o('tail3', 'rx', 0.3 * e); o('tail4', 'rx', 0.35 * e); o('tail5', 'rx', 0.3 * e);
      ears(o, -0.15 * e, 0.2 * e);
      o('ctl', 'lid', 0.55 * e); o('ctl', 'breath', -0.3 * e); o('ctl', 'amp', 0.3 * e);
    } },
    dance: { dur: 2.2, fn(p, o, c) { /* flag, spin and wash (research/squirrel.md 2.14): freeze and snap to the reader; sit up tall and run two
      flags up a fluffed tail; two pivot-hops over the hind feet that turn it right round, a double foot-stamp on each landing;
      three quick face strokes; then down into rest with weight, the tail last, and one slow blink */
      const snap = c.keys(p, [[0.02, 0], [0.075, 1.1], [0.11, 1], [0.3, 1], [0.34, 0.3], [0.64, 0.3], [0.7, 1], [0.86, 1], [0.95, 0], [1, 0]]);
      headTo(o, FACE, snap, -0.25); ears(o, 0.3 * c.env(p, 0.04, 0.1), 0);
      flick(o, c, p, 0.035, 0.55);
      const sitE = c.keys(p, [[0.1, 0], [0.19, 1.06], [0.24, 1], [0.31, 1], [0.35, 0], [1, 0]]);
      const hop1 = c.hop(p, 0.36, 0.465), hop2 = c.hop(p, 0.505, 0.61);
      const crouch = 0.6 * (c.bump(p, 0.33, 0.37) + c.bump(p, 0.455, 0.515) + c.bump(p, 0.6, 0.655));
      const washE = c.keys(p, [[0.63, 0], [0.7, 1], [0.86, 1], [0.92, -0.05], [1, 0]]);
      const hopE = c.keys(p, [[0.33, 0], [0.37, 1], [0.62, 1], [0.66, 0], [1, 0]]);
      /* the body: sitting, crouching, flying, washing, all summed; the hind legs solve for the feet once */
      const beta = -1.0 * sitE - 0.6 * washE - 0.3 * (c.hop(p, 0.36, 0.42) + c.hop(p, 0.505, 0.56)) + 0.18 * (c.hop(p, 0.42, 0.465) + c.hop(p, 0.56, 0.61));
      const lift = -0.09 * sitE + 0.05 * (hop1 + hop2) - 0.025 * crouch - 0.06 * washE;
      const gamma = 0.4 * (hop1 + hop2) + 0.1 * washE;
      o('body', 'rx', beta); o('body', 'py', lift); o('chest', 'rx', gamma);
      const st1 = c.bump(p, 0.465, 0.49) + c.bump(p, 0.49, 0.515), st2 = c.bump(p, 0.61, 0.635) + c.bump(p, 0.635, 0.66);
      limbs(o, { beta, gamma, lift, hind: [[0, 0.02 * st1], [0, 0.02 * st2]], fore: [[0, 0], [0, 0]], free: Math.max(sitE, washE, hopE), toes: 2 });
      o('body', 'rz', 0.04 * (st1 - st2));
      /* the arms: to the chest while sitting, tucked in the air, to the face for the wash */
      arms(o, sitE, -1.45, -1.35, -0.35, 0.5); arms(o, hopE, -1.0, -1.2, -0.3, 0.2); arms(o, washE, -1.6, -1.5, -0.5, 0.3);
      const stroke = c.bump(p, 0.68, 0.86), sw = TAU * 3 * (p - 0.68) / 0.18;
      arms(o, stroke, 0.12 * Math.cos(sw), 0.35 * Math.sin(sw), 0.2 * Math.sin(sw), 0);
      o('neck', 'rx', 0.35 * sitE + 0.2 * washE); o('head', 'rx', 0.55 * sitE + 0.65 * washE + 0.05 * Math.sin(sw) * stroke);
      /* the spin: two pivot-hops over the hind feet, a half turn each */
      const spin = c.keys(p, [[0.33, 0], [0.37, 0.02], [0.465, 0.5], [0.505, 0.52], [0.61, 1], [1, 1]]);
      const a = TAU * spin, PX = -0.2 * Math.sin(-0.85), PZ = -0.2 * Math.cos(-0.85);      /* the pivot: under the hind feet, in root space */
      o('pose', 'ry', spin >= 1 - 1e-9 ? a - TAU : a);
      o('pose', 'px', PX - (PX * Math.cos(a) + PZ * Math.sin(a))); o('pose', 'pz', PZ - (-PX * Math.sin(a) + PZ * Math.cos(a)));
      o('body', 'rz', 0.12 * Math.sin(TAU * spin) * (hop1 + hop2));
      /* the tail: stands up and fluffs for the flags, streams in the hops, re-curls, settles last */
      o('tail1', 'rx', 0.75 * sitE + 0.3 * washE); o('tail3', 'rx', 0.22 * sitE); o('tail4', 'rx', 0.18 * sitE);
      flag(o, p, 9, 0.5 * c.bump(p, 0.12, 0.34), -TAU * 9 * 0.12);
      o('tail2', 's', 0.1 * sitE); o('tail3', 's', 0.08 * sitE);
      const stream = hop1 + hop2;
      o('tail2', 'rx', -0.2 * stream); o('tail3', 'rx', -0.4 * stream); o('tail4', 'rx', -0.45 * stream); o('tail5', 'rx', -0.4 * stream);
      o('ctl', 'lid', 0.9 * c.bump(p, 0.9, 0.99));
      o('ctl', 'look', c.env(p, 0.02, 0.05));
    } },
  };
  K.finish(R);
  K.restTurn(R, 'head', [0, HEAD_YAW, 0]);      /* bound straight, rests turned a little toward the reader; the neck bends into it */
  return R;
}

export default {
  id: 'squirrel',
  name: 'Eastern gray squirrel',
  latin: 'Sciurus carolinensis',
  rests: 'floor',
  build: (THREE, kit) => buildSquirrel(THREE, kit),
  update: (rig, dt, state) => rig.kit.update(rig, dt, state),
  play: (rig, clip, variant) => rig.kit.play(rig, clip, variant),
  rest: (rig) => rig.kit.rest(rig),
};
