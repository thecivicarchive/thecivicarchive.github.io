/*
  The Civic Archive companion: the eastern chipmunk (Tamias striatus).

  Built on the companions' realism kit (kit.js) and the species research in research/chipmunk.md. No licensed model
  worth building on was found (every candidate failed on anatomy, licence or access), so the animal is sculpted in code
  from the measurements: head-and-body 1.0, tail 0.62 of it, hind foot 0.23, skull 0.28, ear 0.13 (Hayssen 2008; Jones &
  Suttkus 1978), in the semi-upright sit a chipmunk rests in (the back arched about 35 degrees, the head level, the
  forepaws held to the chest, the long hind feet flat on the ground in front). Trunk, head, ears, limbs and tail are one
  signed distance field surfaced as one mesh that bends over a skeleton (pelvis, two spine joints, neck, head, cheek
  pouches, ears, nose, each limb in three bones, four tail bones); the coat is painted per vertex from the species sheet
  (five dark stripes, the lower two on each side bordering a pale one, the rusty rump, the grizzled tan, the pale eye
  stripes, the white underparts) and dressed in dense short fur shells, long and frosted on the flattened tail; hands
  and feet are bare skin with claws; the nose is wet; the whiskers sweep with every nose twitch; the eyes are big, black
  and wet. Nothing is loaded from anywhere.

  export default { id, name, latin, rests, build(THREE, kit) -> rig, update(rig, dt, state), play(rig, clip) -> seconds, rest(rig) }
    rig.root   1 unit = the sitting height, facing +z toward the viewer, feet at y = 0
    clips      arrive, idleA, idleB (3: pouch loading, the four-phase face wash, the freeze-and-scan), notice, react
               (the alarm "chip", the tail flicking on every note), talk, lookLeft, lookRight, rest, dance ("the cheeky
               chip"); every clip ends exactly on the rest pose. update() breathes at the flanks, blinks at irregular
               intervals, follows the pointer in quick turns and plays the idles itself.

  Motion, from the research: the bound (both hands land and the nose pitches up; both feet land and it pitches down;
  the spine flexes over the stride; the tail rigid and vertical) that ends in a dead stop, often after a flat reversal
  (Elliott 1978); the rise from the semi-upright sit to the upright stance; the chip at 2.2 Hz with a tail snap on each
  note; nose twitches in 7 Hz bouts with the whiskers; the face wash in its four phases (Kalueff 2016; Berridge 1990);
  the pouches filled one side a beat ahead and emptied with back-to-front strokes (Schwartz & Schwartz 1959); breathing
  at 1.5 Hz; blinks of 70/40/150 ms in the rodent's clusters. Joints move over planted feet: a small two-bone solver in
  the sagittal plane keeps the heels on the ground while the body rises, pitches and crouches.
*/

function buildChipmunk(THREE, K) {
  if (!K || !K.rig) throw new Error('the chipmunk needs the companions kit: build(THREE, kit)');
  const { sd, surf, prim, rgb, mixc, fbm, noise, sst, lerp, clamp, PI, TAU } = K;
  const YAW = -0.8, HEAD_REST = 0.3;      /* the body sits three-quarters to the page; the head rests turned a little toward the reader */
  const R = K.rig({
    id: 'chipmunk', yaw: YAW, frame: { x: [-0.44, 0.6], y: [-0.04, 1.08] }, fov: 34,
    breath: 1.5, look: { yaw: 0.95, pitch: 0.45, speed: 13 },
    idles: ['idleA', 'idleB', 'idleB', 'lookLeft', 'lookRight', 'notice'],
  });

  /* ---------- the sheet: grizzled tan, five dark stripes, pale stripes, rusty rump, white underparts; no red, no blue ---------- */
  const BASE = rgb(0x9a7b57), BASE2 = rgb(0x7f6d5a), GRIZ = rgb(0xcbb48c), DARK = rgb(0x231b14), DARK2 = rgb(0x3b2f25);
  const PALE = rgb(0xf1e9d7), BELLY = rgb(0xe9ddc7), FLANK = rgb(0xb88b60), RUMP = rgb(0xa5633c), RUMP2 = rgb(0x8d5330);
  const SKIN = rgb(0xc9ae92), SKIN2 = rgb(0xa58b72), CLAW = rgb(0x3a2e26), NOSE = rgb(0x30261f), EARIN = rgb(0xd8c3a4), WHISK = rgb(0xe8e2d8);
  const RING = rgb(0xdfcfae), LIDC = mixc(rgb(0x3b2f25), rgb(0x7f6d5a), 0.45);      /* the buffy eye-ring at the lids' margins, the stripe's dark fur over them: a blink reads against the black eye */

  /* ---------- landmarks (sculpt space: +z forward, y up, feet at 0; one unit = the sitting height; head-body is 1.28) ---------- */
  const PELV = [0, 0.26, -0.12], S1P = [0, 0.4, -0.05], S2P = [0, 0.54, 0.02], NKP = [0, 0.66, 0.08], HDP = [0, 0.745, 0.12];
  const HC = [0, 0.795, 0.145], hd = (dx, dy, dz) => [HC[0] + dx, HC[1] + dy, HC[2] + dz];      /* the skull's centre; the head is placed from it */
  const HIP = (s) => [s * 0.12, 0.3, -0.08], KNEE = (s) => [s * 0.175, 0.23, 0.2], HEEL = (s) => [s * 0.16, 0.045, -0.03];
  const SHO = (s) => [s * 0.11, 0.6, 0.08], ELB = (s) => [s * 0.125, 0.45, 0.14], WRI = (s) => [s * 0.075, 0.5, 0.25];
  const TP = [[0, 0.14, -0.3], [0, 0.14, -0.5], [0, 0.3, -0.64], [0, 0.55, -0.66], [0, 0.72, -0.56]];      /* the tail's arc */
  const EAR = (s) => hd(s * 0.072, 0.095, -0.055), CHEEK = (s) => hd(s * 0.085, -0.045, 0.075), NOSEP = hd(0, -0.028, 0.225);
  const POUCH = (s) => hd(s * 0.045, -0.05, 0.07);      /* the pouch's pivot sits inside the cheek, so swelling it domes the whole side of the jaw */

  /* ---------- the body as one field ---------- */
  const rump = sd.egg([0, 0.22, -0.13], [0.2, 0.19, 0.2]);
  const belly = sd.egg([0, 0.38, 0.0], [0.19, 0.2, 0.19]);
  const chest = sd.egg([0, 0.56, 0.06], [0.155, 0.15, 0.15]);
  const shoulders = sd.egg([0, 0.63, 0.03], [0.165, 0.11, 0.14]);
  const neckF = sd.limb([0, 0.64, 0.08], hd(0, -0.075, -0.015), 0.1, 0.09);
  const trunkF = sd.add(0.07, rump, belly, chest, shoulders, neckF);
  const skull = sd.egg(HC, [0.1, 0.098, 0.125]);
  const brow = sd.egg(hd(0, 0.04, 0.05), [0.075, 0.07, 0.08]);
  const muzzle = sd.egg(hd(0, -0.025, 0.13), [0.062, 0.058, 0.085]);
  const muzzleTip = sd.egg(hd(0, -0.03, 0.19), [0.04, 0.038, 0.045]);
  const jaw = sd.egg(hd(0, -0.07, 0.1), [0.062, 0.042, 0.075]);
  const cheekF = (s) => sd.egg(CHEEK(s), [0.056, 0.05, 0.066]);
  const headF = sd.add(0.04, skull, brow, muzzle, muzzleTip, jaw, cheekF(1), cheekF(-1));
  /* small, rounded, erect ears, cupped toward the front and splayed a little outward */
  const earF = (s) => {
    const cup = sd.sub(sd.egg([0, 0, 0], [0.038, 0.047, 0.027]), sd.egg([s * 0.004, 0.012, 0.03], [0.028, 0.036, 0.022]), 0.008);
    return sd.xf(cup, EAR(s), [-0.12, s * 0.35, -s * 0.3]);
  };
  const thigh = (s) => sd.limb(HIP(s), KNEE(s), 0.085, 0.055);
  const shin = (s) => sd.limb(KNEE(s), HEEL(s), 0.06, 0.036);
  const uarm = (s) => sd.limb(SHO(s), ELB(s), 0.05, 0.038);
  const farm = (s) => sd.limb(ELB(s), WRI(s), 0.036, 0.028);
  /* the tail: wider than tall, tapering at both ends, its edge roughened so it reads as hair even before the fur */
  const tailSeg = (A, B, r1, r2) => {
    const c = [(A[0] + B[0]) / 2, (A[1] + B[1]) / 2, (A[2] + B[2]) / 2];
    return sd.xf(sd.limb([A[0] - c[0], A[1] - c[1], A[2] - c[2]], [B[0] - c[0], B[1] - c[1], B[2] - c[2]], r1, r2), c, null, [1.3, 0.9, 1]);
  };
  const furry = (f, amp, fr) => { const g = (x, y, z) => f(x, y, z) + amp * (noise(x * fr, y * fr, z * fr) - 0.45); g.b = f.b ? [f.b[0], f.b[1], f.b[2], f.b[3] + amp] : null; return g; };
  const tailF = furry(sd.add(0.03, tailSeg(TP[0], TP[1], 0.036, 0.05), tailSeg(TP[1], TP[2], 0.05, 0.056), tailSeg(TP[2], TP[3], 0.056, 0.045), tailSeg(TP[3], TP[4], 0.045, 0.026)), 0.0035, 90);
  const limbsF = sd.add(0.04, trunkF, thigh(1), thigh(-1), shin(1), shin(-1), uarm(1), uarm(-1), farm(1), farm(-1));
  const EaL = earF(1), EaR = earF(-1);
  const bodyF = sd.add(0.03, sd.add(0.015, sd.add(0.05, limbsF, headF), EaL, EaR), tailF);

  /* hands hang from the wrists, four fingers curled toward the chest; feet lie flat, five toes forward, all with claws */
  const handF = (s) => {
    const W = WRI(s), parts = [], claws = [];
    parts.push(sd.egg([W[0], W[1] - 0.028, W[2] + 0.004], [0.024, 0.024, 0.018]));
    for (let i = 0; i < 4; i++) {
      const fx = W[0] + s * (-0.018 + 0.012 * i);
      const a = [fx, W[1] - 0.044, W[2] + 0.012], b = [fx, W[1] - 0.078, W[2] + 0.002], t = [fx, W[1] - 0.092, W[2] - 0.01];
      parts.push(sd.limb(a, b, 0.0078, 0.006)); claws.push(sd.limb(b, t, 0.004, 0.0015));
    }
    const clawS = sd.add(0, ...claws);
    return { f: sd.add(0.01, sd.add(0.012, ...parts), clawS), claw: clawS };
  };
  const footF = (s) => {
    const H = HEEL(s), parts = [], claws = [];
    parts.push(sd.xf(sd.limb([0, 0, 0], [0, 0, 0.23], 0.03, 0.028), [H[0], 0.031, H[2] + 0.01], null, [1.05, 0.65, 1]));
    for (let i = 0; i < 5; i++) {
      const tx = (i - 2) * 0.0125, sp = 1 - 0.12 * Math.abs(i - 2);
      const a = [H[0] + tx, 0.022, H[2] + 0.215], b = [H[0] + tx * 1.3, 0.02, H[2] + 0.215 + 0.062 * sp], t = [H[0] + tx * 1.4, 0.016, H[2] + 0.215 + 0.062 * sp + 0.02];
      parts.push(sd.limb(a, b, 0.0105, 0.0075)); claws.push(sd.limb(b, t, 0.0045, 0.0015));
    }
    const clawS = sd.add(0, ...claws);
    return { f: sd.add(0.008, sd.add(0.012, ...parts), clawS), claw: clawS };
  };
  const HdL = handF(1), HdR = handF(-1), FtL = footF(1), FtR = footF(-1);
  const noseF = sd.egg(hd(0, -0.028, 0.232), [0.015, 0.012, 0.011]);
  const all = sd.min(bodyF, HdL.f, HdR.f, FtL.f, FtR.f, noseF);

  /* ---------- where things are on the body: the head, the tail, the spine ---------- */
  const hn = (x, y, z) => (y - 0.69) * 0.9 + (z - 0.115) * 0.44;              /* above the neck plane is the head */
  const inHead = (x, y, z) => sst(-0.03, 0.03, hn(x, y, z));
  const tailness = (x, y, z) => sst(-0.01, 0.03, trunkF(x, y, z) - tailF(x, y, z));
  const SPINE = [[0.1, -0.2], [0.26, -0.13], [0.44, -0.04], [0.6, 0.05], [0.69, 0.1]];      /* (y, z) along the back */
  const SPL = [0];
  for (let i = 1; i < SPINE.length; i++) SPL.push(SPL[i - 1] + Math.hypot(SPINE[i][0] - SPINE[i - 1][0], SPINE[i][1] - SPINE[i - 1][1]));
  /* u runs 0 at the rump to 1 at the nape; phi is the angle around the spine, 0 on the back, +-pi on the belly; d the
     distance from the spine, so d * |phi| is about the distance over the back from the midline */
  const spineAt = (x, y, z) => {
    let best = Infinity, bu = 0, bphi = 0;
    for (let i = 0; i < SPINE.length - 1; i++) {
      const ay = SPINE[i][0], az = SPINE[i][1], by = SPINE[i + 1][0], bz = SPINE[i + 1][1], dy = by - ay, dz = bz - az, l2 = dy * dy + dz * dz;
      const t = clamp(((y - ay) * dy + (z - az) * dz) / l2, 0, 1), py = ay + dy * t, pz = az + dz * t;
      const d = Math.hypot(x, y - py, z - pz);
      if (d < best) {
        best = d; const l = Math.sqrt(l2), ty = dy / l, tz = dz / l, bky = tz, bkz = -ty;
        bu = (SPL[i] + t * l) / SPL[SPL.length - 1]; bphi = Math.atan2(x, (y - py) * bky + (z - pz) * bkz);
      }
    }
    return { u: bu, phi: bphi, d: best };
  };

  /* the eyes: on the sides of the head, looking out and a little forward, found on the surface before anything is painted */
  const EYES = [];
  for (const s of [1, -1]) {
    const yaw = s * 1.08, pit = 0.12;
    const d = [Math.sin(yaw) * Math.cos(pit), Math.sin(pit), Math.cos(yaw) * Math.cos(pit)];
    EYES.push({ s, d, sp: K.hit(headF, hd(0, 0.012, 0.035), d) });
  }
  const EYZ = EYES[0].sp[2] - HC[2], EYY = EYES[0].sp[1] - HC[1];

  /* ---------- the coat ---------- */
  const tailPaint = (x, y, z, g1, g2) => {
    const edge = sst(0.016, 0.05, Math.abs(x));
    const mid = mixc(mixc(DARK2, BASE2, 0.45 + 0.4 * g1), RUMP2, 0.25);
    return mixc(mid, mixc(PALE, GRIZ, 0.35 + 0.4 * g2), 0.78 * edge);
  };
  const coat = (x, y, z, nx, ny, nz) => {
    const g1 = fbm(x * 95, y * 95, z * 95, 2), g2 = noise(x * 190, y * 190, z * 190), w = fbm(x * 26, y * 26, z * 26, 2);
    const griz = 0.3 + 0.45 * g1 + 0.25 * g2;
    const tl = tailness(x, y, z);
    if (tl > 0.999) return tailPaint(x, y, z, g1, g2);
    let c = mixc(mixc(BASE, BASE2, 0.4 * w), GRIZ, 0.5 * griz);      /* grizzled tan: pale tips over dark roots */
    const H = inHead(x, y, z);
    if (H < 0.999) {      /* the trunk and limbs: the stripes are laid out by distance over the back from the midline (a
                             chipmunk's mid-dorsal stripe is about 4 mm wide on a 40 mm back; the lateral set, dark, pale,
                             dark, runs from about 10 to 21 mm out), the flank and belly by the angle round the spine */
      const S = spineAt(x, y, z), a = Math.abs(S.phi), u = S.u, arc = S.d * a;
      const span = sst(0.08, 0.2, u) * (1 - sst(0.84, 0.95, u));
      const band = (c0, hw) => sst(hw, hw * 0.45, Math.abs(arc - c0));
      const mid = band(0, 0.02) * sst(0.1, 0.2, u) * (1 - sst(0.9, 0.97, u));
      const dark = Math.max(mid, band(0.1, 0.017) * span, band(0.166, 0.017) * span), pale = band(0.133, 0.019) * span;
      let b = c;
      b = mixc(b, mixc(RUMP, RUMP2, 0.5 * g1), sst(0.3, 0.1, u) * sst(1.9, 1.3, a));                       /* the rusty rump */
      b = mixc(b, mixc(BASE2, GRIZ, 0.5 * griz), 0.5 * sst(0.75, 0.92, u) * sst(0.12, 0.04, arc));          /* greyer at the nape */
      b = mixc(b, mixc(FLANK, GRIZ, 0.35 * g2), sst(0.17, 0.22, arc) * (1 - sst(1.95, 2.25, a)) * sst(0.06, 0.2, u));   /* warm flanks */
      b = mixc(b, mixc(BELLY, PALE, 0.3 * g2), 0.92 * sst(1.95, 2.3, a));                                /* white underparts */
      b = mixc(b, mixc(DARK, DARK2, 0.4 * g1), 0.94 * dark);
      b = mixc(b, mixc(PALE, GRIZ, 0.15 * g2), 0.94 * pale);
      /* the legs are buff-tan, paler inside; the arms the same, white along the inner forearm */
      const s = x >= 0 ? 1 : -1, leg = Math.min(shin(s)(x, y, z), thigh(s)(x, y, z)), arm = Math.min(uarm(s)(x, y, z), farm(s)(x, y, z));
      const outer = sst(0.07, 0.13, Math.abs(x));
      b = mixc(b, mixc(FLANK, SKIN, 0.3 + 0.3 * g1), 0.7 * sst(0.012, -0.004, leg) * (0.35 + 0.65 * outer) * sst(0.26, 0.12, y));
      b = mixc(b, mixc(FLANK, BASE, 0.5 + 0.3 * g1), 0.65 * sst(0.012, -0.004, arm) * outer);
      c = mixc(b, c, H);
    }
    if (H > 0.001) {      /* the head: the dark stripe through the eye with a pale one above and below, a second dark
                             below, the grizzled crown with the mid-dorsal stripe starting between the ears, white chin */
      const hx = x - HC[0], hy = y - HC[1], hz = z - HC[2], az = Math.abs(Math.atan2(hx, hz));
      const side = sst(0.3, 0.7, az) * (1 - sst(2.0, 2.5, az));
      const el = hy - (EYY - 0.09 * (hz - EYZ));                                          /* height above the eye line */
      const line = (e0, hw) => sst(hw, hw * 0.35, Math.abs(el - e0));
      const fore = sst(0.12, 0.4, az) * (1 - sst(2.0, 2.45, az));      /* the dark stripe runs from the nose through the eye to the ear */
      let h = mixc(c, mixc(BASE2, GRIZ, 0.4 * griz), 0.35);
      h = mixc(h, mixc(PALE, GRIZ, 0.15 * g2), 0.95 * side * line(0.052, 0.024));
      h = mixc(h, mixc(DARK, DARK2, 0.3 * g1), fore * line(0.0, 0.03));
      h = mixc(h, mixc(PALE, GRIZ, 0.15 * g2), 0.95 * side * line(-0.05, 0.023));
      h = mixc(h, mixc(DARK2, BASE2, 0.3), 0.65 * side * line(-0.092, 0.018));
      h = mixc(h, mixc(BELLY, PALE, 0.5), 0.9 * sst(-0.03, -0.075, hy) * sst(0.6, 1.4, az + sst(0.1, 0.25, hz) * 1.2));   /* chin and throat */
      h = mixc(h, mixc(DARK, DARK2, 0.5), 0.75 * sst(0.035, 0.012, Math.abs(hx)) * sst(0.08, 0.0, hz) * sst(0.03, 0.07, hy));   /* the crown stripe */
      h = mixc(h, mixc(GRIZ, BASE2, 0.4), 0.4 * sst(0.17, 0.25, hz));                              /* the muzzle greys */
      const ear = sst(0.03, 0.006, Math.min(EaL(x, y, z), EaR(x, y, z)));
      const inner = sst(0.1, 0.5, nz * 0.8 + Math.abs(nx) * 0.3);
      h = mixc(h, mixc(mixc(DARK2, BASE2, 0.55), EARIN, inner), 0.85 * ear);
      h = mixc(h, PALE, 0.45 * ear * sst(0.12, 0.135, hy) * (1 - inner));                           /* the pale rim behind */
      c = mixc(c, h, H);
    }
    return mixc(c, tailPaint(x, y, z, g1, g2), tl);
  };
  /* the groom: dense short fur combed down and back, shorter on the face and ears, none across the eyes, long and
     combed sideways on the tail so it reads flattened and frosted */
  const groom = (x, y, z, nx, ny, nz) => {
    const H = inHead(x, y, z), tl = tailness(x, y, z), hz = z - HC[2];
    const ear = sst(0.03, 0.006, Math.min(EaL(x, y, z), EaR(x, y, z)));
    let len = lerp(1, 0.62, H) * lerp(1, 0.5, H * sst(0.1, 0.2, hz)) * lerp(1, 0.55, ear);
    for (const E of EYES) len *= sst(0.03, 0.052, Math.hypot(x - E.sp[0], y - E.sp[1], z - E.sp[2]));
    for (const s of [1, -1]) { const W = WRI(s); len *= lerp(0.4, 1, sst(0.035, 0.1, Math.hypot(x - W[0], y - (W[1] - 0.04), z - W[2]))); }      /* short around the hands, so they show */
    len *= 1 + 0.15 * (1 - H) * sst(0.2, 0.5, y) * sst(0.1, 0.25, z);
    len = lerp(len, 1.3, tl);
    const dens = lerp(1, 1.05, tl) * lerp(1, 1.25, H);
    const sx = x >= 0 ? 1 : -1;
    let cx = 0, cy = lerp(-1, -0.35, H), cz = lerp(-0.35, -1, H);
    cx = lerp(cx, sx * 0.75, tl); cy = lerp(cy, 0.55, tl); cz = lerp(cz, -0.3, tl);
    return [len, dens, cx, cy, cz];
  };

  /* ---------- materials ---------- */
  const furM = K.physical({ rough: 0.78, sheen: 0.32, sheenRough: 0.6, spec: 0.28, name: 'chipmunk-fur' });
  const skinM = K.physical({ rough: 0.55, clearcoat: 0.15, ccRough: 0.4, sheen: 0.12, spec: 0.45, name: 'chipmunk-skin' });
  const noseM = K.physical({ rough: 0.28, clearcoat: 0.65, ccRough: 0.15, spec: 0.7, name: 'chipmunk-nose' });
  const whiskM = K.physical({ rough: 0.42, spec: 0.5, sheen: 0.2, name: 'chipmunk-whisker' });

  /* ---------- the skeleton ---------- */
  K.joint(R, 'pelvis', 'pose', PELV);
  K.joint(R, 'spine1', 'pelvis', S1P);
  K.joint(R, 'spine2', 'spine1', S2P);
  K.joint(R, 'neck', 'spine2', NKP);
  K.joint(R, 'head', 'neck', HDP);
  K.joint(R, 'nose', 'head', hd(0, -0.028, 0.2));
  for (const s of [1, -1]) {
    const L = s > 0 ? 'L' : 'R';
    K.joint(R, 'cheek' + L, 'head', POUCH(s));
    K.joint(R, 'ear' + L, 'head', hd(s * 0.07, 0.065, -0.05));
    K.joint(R, 'whisk' + L, 'head', hd(s * 0.048, -0.035, 0.17));
    K.joint(R, 'shoulder' + L, 'spine2', SHO(s));
    K.joint(R, 'elbow' + L, 'shoulder' + L, ELB(s));
    K.joint(R, 'wrist' + L, 'elbow' + L, WRI(s));
    K.joint(R, 'hip' + L, 'pelvis', HIP(s));
    K.joint(R, 'knee' + L, 'hip' + L, KNEE(s));
    K.joint(R, 'ankle' + L, 'knee' + L, HEEL(s));
  }
  K.joint(R, 'tail', 'pelvis', TP[0]);
  K.joint(R, 'tail2', 'tail', TP[1]);
  K.joint(R, 'tail3', 'tail2', TP[2]);
  K.joint(R, 'tail4', 'tail3', TP[3]);
  K.limit(R, 'head', { ry: [-1.3, 1.3], rx: [-0.75, 0.85], rz: [-0.45, 0.45] });
  K.limit(R, 'neck', { ry: [-0.6, 0.6], rx: [-0.9, 0.6] });

  /* ---------- the skinned body ---------- */
  const notHead = (x, y, z) => 1 - inHead(x, y, z);
  const sideOnly = (s, a, b) => (x, y, z) => sst(a, b, s * x);
  /* the pouch: the side of the jaw below the eye, from in front of the ear to the base of the muzzle; its bone is a point
     inside the cheek, so scaling it swells the whole side out and down while the eye and the nose stay where they were */
  const pouch = (s) => (x, y, z) => {
    const hx = x - HC[0], hy = y - HC[1], hz = z - HC[2];
    return inHead(x, y, z) * sst(-0.005, -0.035, hy) * sst(0.015, 0.05, s * hx) * sst(-0.07, -0.02, hz) * (1 - sst(0.13, 0.18, hz));
  };
  const bones = [
    { j: 'pelvis', a: [0, 0.12, -0.16], b: [0, 0.36, -0.08], r: 0.2, only: (x, y, z) => notHead(x, y, z) * (1 - tailness(x, y, z)) },
    { j: 'spine1', a: [0, 0.36, -0.08], b: [0, 0.52, 0.0], r: 0.17, only: notHead },
    { j: 'spine2', a: [0, 0.52, 0.0], b: [0, 0.66, 0.08], r: 0.15, only: notHead },
    { j: 'neck', a: [0, 0.66, 0.08], b: HDP, r: 0.1, only: (x, y, z) => 1 - sst(0.04, 0.1, hn(x, y, z)) },
    { j: 'head', a: HDP, b: hd(0, -0.01, 0.17), r: 0.14, only: inHead },
    { j: 'nose', a: NOSEP, b: NOSEP, r: 0.045, w: 2, only: (x, y, z) => sst(0.14, 0.19, z - HC[2]) },
    { j: 'tail', a: TP[0], b: TP[1], r: 0.06, only: tailness },
    { j: 'tail2', a: TP[1], b: TP[2], r: 0.06, only: tailness },
    { j: 'tail3', a: TP[2], b: TP[3], r: 0.06, only: tailness },
    { j: 'tail4', a: TP[3], b: TP[4], r: 0.05, only: tailness },
  ];
  for (const s of [1, -1]) {
    const L = s > 0 ? 'L' : 'R';
    bones.push(
      { j: 'cheek' + L, a: POUCH(s), b: POUCH(s), r: 0.075, w: 4, only: pouch(s) },
      { j: 'ear' + L, a: hd(s * 0.07, 0.07, -0.05), b: hd(s * 0.085, 0.14, -0.06), r: 0.04, w: 3, only: (x, y, z) => sst(0.05, 0.09, y - HC[1]) * sst(0.03, 0.05, Math.abs(x)) },
      { j: 'hip' + L, a: HIP(s), b: KNEE(s), r: 0.085, only: (x, y, z) => sst(0.0, 0.06, s * x) * notHead(x, y, z) },
      { j: 'knee' + L, a: KNEE(s), b: HEEL(s), r: 0.05, only: sideOnly(s, 0.0, 0.06) },
      { j: 'shoulder' + L, a: SHO(s), b: ELB(s), r: 0.05, only: sideOnly(s, 0.02, 0.08) },
      { j: 'elbow' + L, a: ELB(s), b: WRI(s), r: 0.04, only: sideOnly(s, 0.0, 0.05) },
    );
  }
  const bodyGeo = surf(bodyF, [-0.3, -0.01, -0.73, 0.3, 1.0, 0.43], 0.0118, coat, { ao: all, groom });
  const bodyMesh = K.skin(R, bodyGeo, bones, furM, { smooth: 3, name: 'chipmunk-body' });
  K.fur(R, bodyMesh, { len: 0.028, dens: 150, thin: 0.82, root: 0.66, clump: 0.45, comb: 0.9, droop: 0.2, min: 0.4 });

  /* ---------- the parts: hands, feet, nose, whiskers ---------- */
  const paintHand = (Hd) => (x, y, z, nx, ny, nz) => {
    if (Hd.claw(x, y, z) < 0.003) return CLAW;
    const n = fbm(x * 80, y * 80, z * 80, 2), back = sst(0.1, 0.6, nz);
    return mixc(mixc(SKIN, SKIN2, 0.35 * n + 0.4 * sst(0.47, 0.42, y)), mixc(FLANK, GRIZ, 0.5), 0.55 * back);
  };
  const paintFoot = (Ft) => (x, y, z, nx, ny, nz) => {
    if (Ft.claw(x, y, z) < 0.003) return CLAW;
    const n = fbm(x * 80, y * 80, z * 80, 2), top = sst(0.15, 0.7, ny) * sst(0.2, 0.1, z);
    return mixc(mixc(SKIN, SKIN2, 0.35 * n + 0.3 * sst(0.22, 0.27, z)), mixc(FLANK, BASE, 0.5), 0.7 * top);
  };
  for (const s of [1, -1]) {
    const L = s > 0 ? 'L' : 'R', Hd = s > 0 ? HdL : HdR, Ft = s > 0 ? FtL : FtR, W = WRI(s), H = HEEL(s);
    K.put(R, 'wrist' + L, surf(Hd.f, [W[0] - 0.05, W[1] - 0.115, W[2] - 0.03, W[0] + 0.05, W[1] + 0.005, W[2] + 0.04], 0.0046, paintHand(Hd), { ao: all }), skinM);
    K.put(R, 'ankle' + L, surf(Ft.f, [H[0] - 0.06, -0.005, H[2] - 0.03, H[0] + 0.06, 0.07, H[2] + 0.32], 0.0048, paintFoot(Ft), { ao: all }), skinM);
  }
  K.put(R, 'nose', surf(noseF, [-0.025, HC[1] - 0.05, HC[2] + 0.21, 0.025, HC[1] - 0.005, HC[2] + 0.255], 0.0032, () => NOSE, { ao: all }), noseM);
  /* whiskers: six a side, thin tapered cones fanning sideways and back, in one geometry per side */
  const whiskerGeo = (s) => {
    const rows = [[-0.4, 1.3, 0.17], [-0.22, 1.5, 0.19], [-0.05, 1.75, 0.21], [0.12, 1.95, 0.22], [0.3, 2.1, 0.2], [0.5, 2.2, 0.17]];
    const geos = [];
    for (const [el, az, len] of rows) {
      const g = new THREE.CylinderGeometry(0.0005, 0.0017, len, 4, 1, true);
      g.translate(0, len / 2, 0);
      const dir = new THREE.Vector3(s * Math.cos(el) * Math.sin(az), Math.sin(el), Math.cos(el) * Math.cos(az)).normalize();
      g.applyQuaternion(new THREE.Quaternion().setFromUnitVectors(new THREE.Vector3(0, 1, 0), dir));
      geos.push(g);
    }
    let nv = 0, ni = 0;
    for (const g of geos) { nv += g.attributes.position.count; ni += g.index.count; }
    const P = new Float32Array(nv * 3), N = new Float32Array(nv * 3), I = new Uint16Array(ni);
    let ov = 0, oi = 0;
    for (const g of geos) {
      P.set(g.attributes.position.array, ov * 3); N.set(g.attributes.normal.array, ov * 3);
      const ia = g.index.array; for (let k = 0; k < ia.length; k++) I[oi + k] = ia[k] + ov;
      ov += g.attributes.position.count; oi += ia.length; g.dispose();
    }
    const out = new THREE.BufferGeometry();
    out.setAttribute('position', new THREE.BufferAttribute(P, 3)); out.setAttribute('normal', new THREE.BufferAttribute(N, 3)); out.setIndex(new THREE.BufferAttribute(I, 1));
    return prim(out, WHISK, 1);
  };
  K.put(R, 'whiskL', whiskerGeo(1), whiskM, true);
  K.put(R, 'whiskR', whiskerGeo(-1), K.physical({ rough: 0.42, spec: 0.5, sheen: 0.2, name: 'chipmunk-whisker-r' }), true);

  /* ---------- eyes: big, black and wet, in the dark stripe; the lids wear the buffy eye-ring, so a blink reads ---------- */
  for (const E of EYES) {
    const { s, d, sp } = E, r = 0.025, c = [sp[0] - d[0] * r * 0.5, sp[1] - d[1] * r * 0.5, sp[2] - d[2] * r * 0.5], name = s > 0 ? 'eyeL' : 'eyeR';
    /* the lid is a cap around its +y pole; painted by height along that axis: the stripe's dark fur over the lid, the buffy
       eye-ring only in the band at its margin (the last 10 degrees before the rim), so a shut eye reads as fur, not a ball */
    const lidR = r * 1.1, lidPaint = (a, b) => (x, y, z) => mixc(LIDC, RING, sst(a, b, -y / lidR));
    K.eye(R, name, 'head', c, d, r, { iris: 0x110b07, iris2: 0x1c120b, pupil: 0.74, irisAngle: 1.25, sclera: 0x1a120d, limbal: 0x070403, lid: lidPaint(-0.2, -0.06), lidLo: lidPaint(-0.95, -0.78), lidScale: 1.1,
      lidMat: { rough: 0.85, sheen: 0.18, name: name + '-lid' }, open: -0.95, shut: 1.55, glint: 0.26, lowerShare: 0.3, gloss: 0.7, wet: 0.45 });      /* the glint stays inside the shut lid */
  }

  /* ---------- secondary motion: the tail follows through, the ears jiggle on a landing ---------- */
  const dirOf = (A, B) => [B[0] - A[0], B[1] - A[1], B[2] - A[2]];
  K.spring(R, 'tail2', { ch: 'rx', k: 150, c: 11, gain: 0.05, dir: dirOf(TP[1], TP[2]), lim: [-0.45, 0.45] });
  K.spring(R, 'tail3', { ch: 'rx', k: 120, c: 9, gain: 0.06, dir: dirOf(TP[2], TP[3]), lim: [-0.5, 0.5] });
  K.spring(R, 'tail4', { ch: 'rx', k: 100, c: 8, gain: 0.07, dir: dirOf(TP[3], TP[4]), lim: [-0.6, 0.6] });
  K.spring(R, 'earL', { ch: 'rx', k: 420, c: 22, gain: 0.012, dir: [0, 1, 0], lim: [-0.35, 0.35] });
  K.spring(R, 'earR', { ch: 'rx', k: 420, c: 22, gain: 0.012, dir: [0, 1, 0], lim: [-0.35, 0.35] });

  /* ---------- posture: a small two-bone solver in the sagittal plane keeps the heels and paws where they are put ---------- */
  const rotYZ = (y, z, a) => { const c = Math.cos(a), s = Math.sin(a); return [y * c - z * s, y * s + z * c]; };
  const about = (p, c, a) => { const r = rotYZ(p[0] - c[0], p[1] - c[1], a); return [r[0] + c[0], r[1] + c[1]]; };
  const wrap = (a) => Math.atan2(Math.sin(a), Math.cos(a));
  /* two bones L1, L2 from the joint at (jy, jz) reaching for (ty, tz); bend picks the side the middle joint goes to;
     returns the two bones' angles in the plane (atan2(z, y), so a positive rx adds to them) */
  const solve2 = (jy, jz, L1, L2, ty, tz, bend) => {
    const vy = ty - jy, vz = tz - jz, d = clamp(Math.hypot(vy, vz), Math.abs(L1 - L2) + 1e-4, L1 + L2 - 1e-4);
    const av = Math.atan2(vz, vy);
    const a1 = av + bend * Math.acos(clamp((L1 * L1 + d * d - L2 * L2) / (2 * L1 * d), -1, 1));
    const Kn = Math.acos(clamp((L1 * L1 + L2 * L2 - d * d) / (2 * L1 * L2), -1, 1));
    return [a1, a1 - bend * (PI - Kn)];
  };
  const yz = (p) => [p[1], p[2]], dyz = (A, B) => Math.hypot(B[1] - A[1], B[2] - A[2]);
  const HIP1 = HIP(1), KNEE1 = KNEE(1), HEEL1 = HEEL(1), SHO1 = SHO(1), ELB1 = ELB(1), WRI1 = WRI(1);
  const Lh1 = dyz(HIP1, KNEE1), Lh2 = dyz(KNEE1, HEEL1), La1 = dyz(SHO1, ELB1), La2 = dyz(ELB1, WRI1);
  const [LA1, LA2] = solve2(HIP1[1], HIP1[2], Lh1, Lh2, HEEL1[1], HEEL1[2], -1);
  const [AA1, AA2] = solve2(SHO1[1], SHO1[2], La1, La2, WRI1[1], WRI1[2], 1);
  const P0 = yz(PELV);
  /* B = { rho, dy, dz, s1, s2, nk, hd }: the pelvis pitched by rho about its pivot and moved by (dy, dz), the spine bent */
  const pelvisPt = (p, B) => { const r = about(p, P0, B.rho || 0); return [r[0] + (B.dy || 0), r[1] + (B.dz || 0)]; };
  const trunkPt = (p, B) => {
    const c1 = pelvisPt(yz(S1P), B), c2 = about(pelvisPt(yz(S2P), B), c1, B.s1 || 0);
    return about(about(pelvisPt(p, B), c1, B.s1 || 0), c2, B.s2 || 0);
  };
  const poseTrunk = (o, B) => {
    if (B.rho) o('pelvis', 'rx', B.rho); if (B.dy) o('pelvis', 'py', B.dy); if (B.dz) o('pelvis', 'pz', B.dz);
    if (B.s1) o('spine1', 'rx', B.s1); if (B.s2) o('spine2', 'rx', B.s2); if (B.nk) o('neck', 'rx', B.nk); if (B.hd) o('head', 'rx', B.hd);
  };
  /* the hind legs: each heel reaches for (ty, tz) with the sole turned by rot (0 = flat on the ground) */
  const hindLegs = (o, B, ty, tz, rot, sides) => {
    const H = pelvisPt(yz(HIP1), B), [a1, a2] = solve2(H[0], H[1], Lh1, Lh2, ty, tz, -1);
    const hip = wrap(a1 - LA1) - (B.rho || 0), knee = wrap((a2 - a1) - (LA2 - LA1)), ankle = (rot || 0) - wrap(a2 - LA2);
    for (const s of sides || 'LR') { o('hip' + s, 'rx', hip); o('knee' + s, 'rx', knee); o('ankle' + s, 'rx', ankle); }
  };
  /* the forelimbs: each wrist reaches for (ty, tz), the hand turned by rot (0 = hanging as at rest, -pi/2 = flat, fingers forward) */
  const foreLegs = (o, B, ty, tz, rot, sides) => {
    const S = trunkPt(yz(SHO1), B), tot = (B.rho || 0) + (B.s1 || 0) + (B.s2 || 0), [a1, a2] = solve2(S[0], S[1], La1, La2, ty, tz, 1);
    const sh = wrap(a1 - AA1) - tot, el = wrap((a2 - a1) - (AA2 - AA1)), wr = (rot || 0) - wrap(a2 - AA2);
    for (const s of sides || 'LR') { o('shoulder' + s, 'rx', sh); o('elbow' + s, 'rx', el); o('wrist' + s, 'rx', wr); }
  };
  /* the upright bipedal stance, k of the way from the semi-upright sit: the back straightens from 35 to 15 degrees,
     the body lifts, the head stays level, the paws come together at the chest, the ears come forward */
  const UPB = (k) => ({ rho: -0.3 * k, dy: 0.028 * k, dz: 0.012 * k, s1: -0.13 * k, s2: -0.08 * k, nk: 0.27 * k, hd: 0.2 * k });
  const upright = (o, k, B, legs) => {      /* legs === false: the caller places the heels itself (a hop) */
    B = B || UPB(k); poseTrunk(o, B); if (legs !== false) hindLegs(o, B, HEEL1[1], HEEL1[2], 0);
    o('shoulderL', 'rz', -0.12 * k); o('shoulderR', 'rz', 0.12 * k); o('elbowL', 'rx', -0.1 * k); o('elbowR', 'rx', -0.1 * k);
    o('earL', 'rx', 0.15 * k); o('earR', 'rx', 0.15 * k);
  };
  /* the pouches: full, they bulge out and down at the sides of the jaw (the head reads twice its width), the eyes stay put */
  const puff = (o, kl, kr) => {
    for (const [s, k, sg] of [['L', kl, 1], ['R', kr, -1]]) {
      if (!k) continue;
      o('cheek' + s, 'sx', 1.25 * k); o('cheek' + s, 'sy', 0.6 * k); o('cheek' + s, 'sz', 0.4 * k); o('cheek' + s, 'px', sg * 0.02 * k); o('cheek' + s, 'py', -0.012 * k);
    }
  };
  /* a nose-twitch bout: the nose tip lifts and wags at hz, the whiskers sweep forward with it, the head bobs a degree */
  const twitch = (o, t, k, hz) => {
    if (!k) return;
    const tw = Math.sin(t * TAU * hz);
    o('nose', 'py', 0.0045 * (0.5 + 0.5 * tw) * k); o('nose', 'rz', 0.12 * Math.sin(t * TAU * hz + 0.9) * k); o('nose', 'rx', -0.1 * (0.5 + 0.5 * tw) * k);
    o('whiskL', 'ry', 0.24 * tw * k); o('whiskR', 'ry', -0.24 * tw * k);
    o('head', 'rx', -0.025 * tw * k);
  };
  /* a snap: up in `up`, relaxing over `down` (both as shares of the clip) */
  const snap = (p, t0, up, down) => (p <= t0 ? 0 : p < t0 + up ? sst(t0, t0 + up, p) : 1 - sst(t0 + up, t0 + up + down, p));
  /* one alarm note: a 50 ms jerk of the whole animal, a nod up, the tail base snapping up 35 degrees in 80 ms and
     relaxing over 0.3 s; the tip lags on its springs and overshoots */
  const chipNote = (o, p, tc, dur) => {
    const j = Math.sin(PI * clamp((p - tc) / (0.05 / dur), 0, 1)) ** 2 * (p > tc && p < tc + 0.05 / dur ? 1 : 0);
    o('pelvis', 'py', 0.01 * j); o('head', 'rx', -0.09 * snap(p, tc, 0.02 / dur, 0.15 / dur));
    o('tail', 'rx', 0.6 * snap(p, tc, 0.08 / dur, 0.3 / dur)); o('tail2', 'rx', 0.3 * snap(p, tc + 0.04 / dur, 0.08 / dur, 0.3 / dur));
  };
  const FACE_H = 0.35, FACE_N = 0.15;      /* how far the head (and neck) turn to look straight at the reader */
  const face = (o, k) => { o('head', 'ry', FACE_H * k); o('neck', 'ry', FACE_N * k); };

  /* ---------- breathing, attention, the small life that never stops ---------- */
  R.spec.life = (o, L) => {
    const b = L.b, t = L.t;
    o('spine1', 'sx', 0.02 * b); o('spine1', 'sz', 0.028 * b); o('pelvis', 'sz', 0.012 * b); o('pelvis', 'py', 0.006 * b);
    o('spine2', 'rx', -0.012 * b); o('neck', 'rx', 0.008 * b);
    o('head', 'ry', 0.72 * L.yaw); o('neck', 'ry', 0.28 * L.yaw); o('head', 'rz', -0.1 * L.yaw);
    o('head', 'rx', 0.7 * L.pitch); o('neck', 'rx', 0.3 * L.pitch);
    if (L.still) return;
    /* nose-twitch bouts of about a second every 5 to 9 s, at 7 Hz */
    twitch(o, t, sst(0.6, 0.78, 0.5 + 0.5 * Math.sin(t * 0.82 + 0.8 * Math.sin(t * 0.31 + 1))), 7);
    /* a rare quick half-flatten of one ear */
    const flick = (ph) => { const s = Math.sin(t * 0.37 + ph); return s > 0.9995 ? Math.sin(((s - 0.9995) / 0.0005) * PI) : 0; };
    o('earL', 'rx', -0.35 * flick(0)); o('earR', 'rx', -0.35 * flick(2.3));
    /* the tail curls slowly and the tip twitches now and then; the body sways a hair */
    o('tail3', 'rx', 0.05 * Math.sin(t * 0.55)); o('tail4', 'rx', 0.07 * Math.sin(t * 0.55 + 1.2));
    const tt = Math.sin(t * 0.41 + 0.5); o('tail4', 'rx', tt > 0.9993 ? 0.3 * Math.sin(((tt - 0.9993) / 0.0007) * PI) : 0);
    o('pelvis', 'rz', 0.012 * Math.sin(t * 0.19)); o('spine1', 'rz', -0.008 * Math.sin(t * 0.19));
  };

  /* ---------- clips ---------- */
  const FL = -PI / 2 - YAW, FR = PI / 2 - YAW;      /* facing the page (left) and facing away (right), as turns of the pose */
  /* one bound, by phase: both hind feet land at 0 (the nose pitches down, the spine arched), push off by 0.33 (hollow),
     both hands land at 0.5 (the nose pitches up) and leave by 0.82; the body rides highest mid-flight (Lammers &
     Zurcher 2011; Schilling & Hackert 2006). amp scales the bob and the leg swing as the dart slows */
  const bound = (ph, amp) => {
    const bob = 0.04 * amp * (0.5 - 0.5 * Math.cos(TAU * (ph - 0.15)));
    const pitch = 0.16 * amp * Math.cos(TAU * ph);
    const flex = 0.22 * amp * Math.cos(TAU * (ph + 0.08));
    const B = { rho: 1.05 + pitch, dy: bob, dz: 0, s1: 0.55 * flex, s2: 0.45 * flex, nk: -0.6 - 0.25 * flex, hd: -0.5 - 0.4 * pitch };
    let hz, hy, fz, fy, frot;
    if (ph < 0.33) { const u = ph / 0.33; hz = lerp(-0.04, -0.46, u); hy = 0.045; }
    else { const u = (ph - 0.33) / 0.67; hz = lerp(-0.46, -0.04, sst(0, 1, u)); hy = 0.045 + 0.13 * Math.sin(PI * u) * amp; }
    if (ph >= 0.5 && ph < 0.82) { const u = (ph - 0.5) / 0.32; fz = lerp(0.5, 0.18, u); fy = 0.03; frot = -PI / 2; }
    else { const u = ph >= 0.82 ? (ph - 0.82) / 0.68 : (ph + 0.18) / 0.68; fz = lerp(0.18, 0.5, sst(0, 1, u)); fy = 0.03 + 0.14 * Math.sin(PI * u) * amp; frot = -0.9; }
    return { B, hz, hy, fz, fy, frot };
  };
  /* the whole animal between the sit (q = 0) and a quadrupedal pose Q = {B, hz, hy, fz, fy, frot} (q = 1): the feet
     stay planted at every q; the hands come back to the chest as q falls; the tail goes rigid and vertical */
  const quad = (o, q, Q) => {
    const B = { rho: Q.B.rho * q, dy: Q.B.dy * q, dz: Q.B.dz * q, s1: Q.B.s1 * q, s2: Q.B.s2 * q, nk: Q.B.nk * q, hd: Q.B.hd * q };
    poseTrunk(o, B);
    hindLegs(o, B, lerp(HEEL1[1], Q.hy, q), lerp(HEEL1[2], Q.hz, q), 0);
    const W = trunkPt(yz(WRI1), B);      /* where the wrists would hang at the chest with this trunk */
    foreLegs(o, B, lerp(W[0], Q.fy, q), lerp(W[1], Q.fz, q), Q.frot * q);
    o('tail', 'rx', 0.52 * q); o('tail2', 'rx', -0.85 * q); o('tail3', 'rx', -0.64 * q); o('tail4', 'rx', -0.61 * q);
  };
  const FREEZE = { B: { rho: 1.0, dy: 0.01, dz: 0, s1: 0.08, s2: 0.04, nk: -0.78, hd: -0.55 }, hz: -0.14, hy: 0.045, fz: 0.42, fy: 0.03, frot: -PI / 2 };

  R.clips = {
    arrive: { dur: 2.0, fn(p, o, c) { /* a dart in from the right, a flat reversal, a dead stop on all fours with the head
                                        up, then it sits up and turns to the page (Elliott 1978; McAdam & Kramer 1998) */
      const t = p * 2.0;
      /* travel: in fast and slowing, a reversal, one bound back, then still */
      let x;
      if (t < 0.52) { const u = t / 0.52; x = 1.25 - 1.37 * (1 - (1 - u) * (1 - u)); }
      else if (t < 0.64) x = -0.12;
      else if (t < 0.88) x = -0.12 + 0.12 * sst(0, 1, (t - 0.64) / 0.24);
      else x = 0;
      o('mover', 'px', x);
      /* facing: left while darting, a 180 degree pivot in 0.2 s, right while frozen, round to the page as it sits up */
      let ry;
      if (t < 0.56) ry = FL;
      else if (t < 0.76) ry = lerp(FL, FR, sst(0, 1, (t - 0.56) / 0.2));
      else if (t < 1.1) ry = FR;
      else ry = FR * (1 - sst(0, 1, (t - 1.1) / 0.36));
      o('pose', 'ry', ry);
      /* the body: bounding, then crouched for the pivot, one bound, frozen, up into the sit */
      const q = 1 - sst(1.1, 1.46, t);
      if (t < 0.52) { const ph = (t * 5.5) % 1, amp = 1 - 0.5 * sst(0.3, 0.52, t); quad(o, 1, bound(ph, amp)); }
      else if (t < 0.64) { const k = sst(0.52, 0.58, t); const Q = bound(0, 0.5); Q.B = Object.assign({}, Q.B, { rho: 1.05 - 0.25 * k, dy: -0.03 * k }); quad(o, 1, Q); o('mover', 'py', 0.035 * c.hop(t / 2, 0.29, 0.335)); }
      else if (t < 0.88) { const ph = (t - 0.64) / 0.24; quad(o, 1, bound(ph, 0.8)); }
      else { quad(o, q, FREEZE); }
      /* frozen: fast breathing, the nose working, ears forward, eyes above the back line */
      const fz = c.bump(p, 0.42, 0.62);
      o('ctl', 'breath', 1.2 * fz); o('ctl', 'amp', 0.6 * fz);
      twitch(o, t, sst(0.86, 0.95, t) * (1 - sst(1.5, 1.9, t)), 9);
      o('earL', 'rx', 0.25 * q); o('earR', 'rx', 0.25 * q);
      /* settling in the sit: a look at the reader, let go; a cluster of three blinks after the dart */
      face(o, c.bump(p, 0.72, 0.98));
      o('ctl', 'lid', c.bump(p, 0.6, 0.65) + c.bump(p, 0.78, 0.83) + c.bump(p, 0.92, 0.97));
      o('ctl', 'look', 1 - c.ramp(t, 1.6, 1.95));
    } },
    idleA: { dur: 4.6, fn(p, o, c) { /* breathing with a deeper breath, a slow shift of weight, two quick looks with holds, a tail-tip twitch */
      o('ctl', 'amp', 0.7 * c.bump(p, 0.1, 0.7));
      const e = c.env(p, 0.2, 0.25);
      o('pelvis', 'rz', 0.03 * Math.sin(c.TAU * p) * e); o('spine1', 'rz', -0.02 * Math.sin(c.TAU * p) * e); o('head', 'rz', 0.04 * Math.sin(c.TAU * p) * e);
      const ry = c.keys(p, [[0, 0], [0.3, 0], [0.335, 0.5], [0.52, 0.5], [0.55, -0.32], [0.72, -0.32], [0.76, 0], [1, 0]]);
      o('head', 'ry', 0.75 * ry); o('neck', 'ry', 0.25 * ry); o('head', 'rz', -0.08 * ry);
      o('tail4', 'rx', 0.3 * c.bump(p, 0.6, 0.67));
      o('ctl', 'look', c.bump(p, 0.27, 0.82));
    } },
    idleB: { variants: 3, dur: (v) => [3.2, 3.6, 2.6][v], fn(p, o, c) {
      if (c.v === 0) { /* loading the pouches: head down to the paws, four pick-and-push strokes, the cheeks swelling in steps
                          (the left a beat ahead), a still moment with the face widened, then two back-to-front strokes empty them */
        const e = c.keys(p, [[0, 0], [0.1, 1], [0.48, 1], [0.6, 0.15], [0.7, 0.15], [0.78, 1], [0.9, 1], [1, 0]]);
        o('head', 'rx', 0.44 * e); o('neck', 'rx', 0.1 * e);
        o('shoulderL', 'rx', -0.55 * e); o('shoulderR', 'rx', -0.55 * e); o('elbowL', 'rx', -0.5 * e); o('elbowR', 'rx', -0.5 * e); o('wristL', 'rx', 0.35 * e); o('wristR', 'rx', 0.35 * e);
        let st = 0, jerk = 0;
        for (let i = 0; i < 4; i++) { const t0 = 0.12 + i * 0.09; st += c.bump(p, t0, t0 + 0.07); jerk += c.bump(p, t0 + 0.045, t0 + 0.085); }
        o('shoulderL', 'rx', -0.18 * st); o('shoulderR', 'rx', -0.18 * st); o('elbowL', 'rx', -0.2 * st); o('elbowR', 'rx', -0.2 * st);
        o('head', 'ry', 0.08 * jerk); o('head', 'rx', -0.05 * jerk);
        puff(o, c.keys(p, [[0, 0], [0.16, 0], [0.19, 0.35], [0.25, 0.35], [0.28, 0.68], [0.34, 0.68], [0.37, 1], [0.72, 1], [0.76, 0.55], [0.8, 0.55], [0.84, 0.08], [0.9, 0]]),
                 c.keys(p, [[0, 0], [0.2, 0], [0.23, 0.33], [0.29, 0.33], [0.32, 0.66], [0.38, 0.66], [0.41, 1], [0.72, 1], [0.77, 0.6], [0.81, 0.6], [0.85, 0.1], [0.9, 0]]));
        o('ctl', 'breath', -0.25 * c.bump(p, 0.5, 0.78));
        const emp = c.bump(p, 0.72, 0.8) + c.bump(p, 0.8, 0.88);
        o('shoulderL', 'rx', -0.3 * emp); o('shoulderR', 'rx', -0.3 * emp); o('wristL', 'rz', -0.3 * emp); o('wristR', 'rz', 0.3 * emp);
        o('ctl', 'look', e);
      } else if (c.v === 1) { /* the face wash in its four phases: elliptical strokes about the nose, big one-paw strokes
                                 with the head tilting away, two-paw sweeps over the flattened ears, then it comes up */
        const e = c.keys(p, [[0, 0], [0.08, 1], [0.86, 1], [1, 0]]);
        o('pelvis', 'rx', -0.1 * e); hindLegs(o, { rho: -0.1 * e }, HEEL1[1], HEEL1[2], 0);
        o('head', 'rx', 0.52 * e); o('neck', 'rx', 0.08 * e);
        o('shoulderL', 'rx', -0.55 * e); o('shoulderR', 'rx', -0.55 * e); o('elbowL', 'rx', -0.7 * e); o('elbowR', 'rx', -0.7 * e); o('wristL', 'rx', 0.5 * e); o('wristR', 'rx', 0.5 * e);
        const ph1 = c.bump(p, 0.08, 0.34), w1 = c.TAU * 7 * 3.6 * p;
        o('shoulderL', 'rx', 0.08 * Math.sin(w1) * ph1); o('shoulderR', 'rx', 0.08 * Math.sin(w1) * ph1);
        o('elbowL', 'rx', 0.14 * Math.cos(w1) * ph1); o('elbowR', 'rx', 0.14 * Math.cos(w1) * ph1);
        o('head', 'rx', 0.03 * Math.sin(w1) * ph1);
        const ph2 = c.bump(p, 0.32, 0.62), w2 = c.TAU * 3 * 3.6 * p, sw = Math.sin(w2);
        o('shoulderL', 'rx', -0.25 * Math.max(0, sw) * ph2); o('shoulderL', 'rz', -0.2 * Math.max(0, sw) * ph2);
        o('shoulderR', 'rx', -0.25 * Math.max(0, -sw) * ph2); o('shoulderR', 'rz', 0.2 * Math.max(0, -sw) * ph2);
        o('head', 'rz', -0.26 * sw * ph2); o('head', 'ry', 0.1 * sw * ph2);
        const ph3 = c.bump(p, 0.6, 0.85), w3 = c.TAU * 2.5 * 3.6 * p, up = 0.5 + 0.5 * Math.sin(w3);
        o('shoulderL', 'rx', -0.4 * up * ph3); o('shoulderR', 'rx', -0.4 * up * ph3); o('elbowL', 'rx', -0.2 * up * ph3); o('elbowR', 'rx', -0.2 * up * ph3);
        o('head', 'rx', -0.2 * up * ph3); o('earL', 'rx', -0.6 * up * ph3); o('earR', 'rx', -0.6 * up * ph3);
        o('ctl', 'lid', 0.8 * c.bump(p, 0.3, 0.88)); o('ctl', 'look', e);
      } else { /* the freeze-and-scan: motionless but for the head, which rises until the eyes are above the back and turns
                  in quick 30 to 60 degree snaps with holds; one tail flick; then it lets go */
        const e = c.keys(p, [[0, 0], [0.1, 1], [0.84, 1], [1, 0]]);
        o('ctl', 'amp', -0.5 * e); o('neck', 'rx', -0.22 * e); o('head', 'rx', -0.12 * e); o('earL', 'rx', 0.2 * e); o('earR', 'rx', 0.2 * e);
        const ry = c.keys(p, [[0, 0], [0.12, 0], [0.16, 0.55], [0.36, 0.55], [0.4, -0.4], [0.58, -0.4], [0.62, 0.2], [0.76, 0.2], [0.8, 0], [1, 0]]);
        o('head', 'ry', 0.75 * ry); o('neck', 'ry', 0.25 * ry); o('head', 'rz', -0.08 * ry);
        o('tail', 'rx', 0.4 * snap(p, 0.46, 0.03, 0.12)); o('tail2', 'rx', 0.2 * snap(p, 0.48, 0.03, 0.12));
        o('ctl', 'look', e);
      }
    } },
    notice: { dur: 1.2, fn(p, o, c) { /* rises to the upright stance in a quarter second and turns to the reader, holds, sits back */
      const k = c.keys(p, [[0, 0], [0.17, 1.06], [0.25, 1], [0.72, 1], [1, 0]]);
      upright(o, k);
      const f = c.keys(p, [[0, 0], [0.08, 1.1], [0.14, 1], [0.72, 1], [0.86, 0], [1, 0]]);
      face(o, f); o('head', 'rx', -0.06 * f);
      o('ctl', 'look', c.env(p, 0.06, 0.14));
    } },
    react: { dur: 1.5, fn(p, o, c) { /* the alarm: bolt upright in 0.15 s, then three chips at 2.2 Hz, each with its tail snap,
                                       ears forward, eyes wide; a cluster of blinks as it settles */
      const k = c.keys(p, [[0, 0], [0.1, 1.05], [0.16, 1], [0.78, 1], [1, 0]]);
      upright(o, k); face(o, 0.8 * k); o('head', 'rx', -0.08 * k); o('earL', 'rx', 0.12 * k); o('earR', 'rx', 0.12 * k);
      for (const tc of [0.133, 0.433, 0.733]) chipNote(o, p, tc, 1.5);
      twitch(o, p * 1.5, c.bump(p, 0.1, 0.8), 8);
      o('ctl', 'lid', c.bump(p, 0.82, 0.87) + c.bump(p, 0.9, 0.95));
      o('ctl', 'look', k);
    } },
    talk: { dur: 3, fn(p, o, c) { /* attentive: faces the reader, small nods and tilts, the nose working, the paws fidgeting */
      const e = c.env(p, 0.12, 0.2);
      face(o, e); o('head', 'rx', 0.07 * Math.sin(c.TAU * 3 * p) * e); o('head', 'rz', 0.12 * Math.sin(c.TAU * 0.5 * p + 0.5) * e);
      twitch(o, p * 3, e * c.bump(p, 0.15, 0.75), 8);
      o('wristL', 'rx', 0.15 * Math.sin(c.TAU * 1.5 * p) * e); o('wristR', 'rx', -0.15 * Math.sin(c.TAU * 1.5 * p) * e);
      o('tail4', 'rx', 0.15 * Math.sin(c.TAU * 1.2 * p) * e); o('earL', 'rx', 0.12 * e); o('earR', 'rx', 0.12 * e);
      o('ctl', 'look', 0.7 * e);
    } },
    lookLeft: { dur: 1.0, fn(p, o, c) { /* a quick turn to the page, a hold, back */
      const e = c.keys(p, [[0, 0], [0.12, 1.08], [0.2, 1], [0.72, 1], [0.86, 0], [1, 0]]);
      o('head', 'ry', -0.8 * e); o('neck', 'ry', -0.2 * e); o('spine2', 'ry', -0.07 * e); o('head', 'rz', 0.05 * e);
      o('ctl', 'look', c.env(p, 0.08, 0.15));
    } },
    lookRight: { dur: 1.0, fn(p, o, c) { /* over the shoulder: the head turns as far as it goes and the trunk twists the rest */
      const e = c.keys(p, [[0, 0], [0.12, 1.08], [0.2, 1], [0.72, 1], [0.86, 0], [1, 0]]);
      o('head', 'ry', 1.1 * e); o('neck', 'ry', 0.35 * e); o('spine2', 'ry', 0.3 * e); o('pelvis', 'ry', 0.3 * e); o('head', 'rz', -0.05 * e);
      o('ctl', 'look', c.env(p, 0.08, 0.15));
    } },
    rest: { dur: 5, fn(p, o, c) { /* dozing: hunched and round, eyes almost shut, slow breathing, the tail curled close */
      const e = c.env(p, 0.25, 0.25);
      o('ctl', 'lid', 0.6 * e); o('ctl', 'breath', -0.4 * e); o('ctl', 'amp', -0.2 * e);
      const B = { rho: 0.06 * e, dy: -0.015 * e, dz: 0, s1: 0.12 * e, s2: 0.04 * e, nk: 0.2 * e, hd: 0.15 * e };
      poseTrunk(o, B); hindLegs(o, B, HEEL1[1], HEEL1[2], 0);
      o('earL', 'rx', -0.15 * e); o('earR', 'rx', -0.15 * e);
      o('tail', 'rx', -0.15 * e); o('tail2', 'rx', 0.2 * e); o('tail3', 'rx', 0.3 * e);
      o('pelvis', 'rz', 0.012 * Math.sin(c.TAU * 2 * p) * e);
    } },
    dance: { dur: 2.2, fn(p, o, c) { /* "the cheeky chip" (research section 5): the alert rise, two chips with their tail
                                       flicks, three cheek-stuffing strokes with the pouches swelling, a hop that empties them,
                                       and back to the sit, every joint home by the end */
      const D = 2.2, t = p * D;
      const k = c.keys(p, [[0, 0], [0.07, 1.05], [0.091, 1], [0.886, 1], [1, 0]]);
      const crouch = c.bump(p, 1.6 / D, 1.68 / D), hop = c.hop(p, 1.68 / D, 1.85 / D), land = c.bump(p, 1.85 / D, 1.95 / D);
      const B = UPB(k); B.dy += -0.06 * crouch - 0.05 * land; B.rho += 0.15 * crouch + 0.1 * land;
      upright(o, k, B, false); hindLegs(o, B, HEEL1[1] + 0.09 * hop, HEEL1[2] + 0.03 * hop, 0.55 * hop);      /* in the air the feet tuck up under it */
      o('mover', 'py', 0.09 * hop);
      face(o, 0.9 * k);
      for (const tc of [0.2 / D, 0.65 / D]) chipNote(o, p, tc, D);
      twitch(o, t, c.bump(p, 0.2 / D, 1.1 / D), 8);
      o('tail', 'rx', 0.35 * c.bump(p, 0, 1.1 / D) + 0.17 * c.bump(p, 1.1 / D, 1.6 / D) + 0.87 * hop);
      /* the stuffing: head to the paws, both paws to the mouth alternating a beat apart */
      const stuff = c.bump(p, 1.08 / D, 1.62 / D), ws = c.TAU * 6 * t;
      o('head', 'rx', 0.44 * stuff); o('neck', 'rx', 0.06 * stuff);
      o('shoulderL', 'rx', (-0.45 + 0.12 * Math.sin(ws)) * stuff); o('shoulderR', 'rx', (-0.45 + 0.12 * Math.cos(ws)) * stuff);
      o('elbowL', 'rx', -0.5 * stuff); o('elbowR', 'rx', -0.5 * stuff); o('wristL', 'rx', 0.3 * stuff); o('wristR', 'rx', 0.3 * stuff);
      puff(o, c.keys(p, [[0, 0], [1.1 / D, 0], [1.3 / D, 0.8], [1.6 / D, 0.8], [1.68 / D, 0.3], [1.78 / D, 0.3], [1.9 / D, 0]]),
              c.keys(p, [[0, 0], [1.2 / D, 0], [1.42 / D, 0.8], [1.6 / D, 0.8], [1.7 / D, 0.3], [1.8 / D, 0.3], [1.9 / D, 0]]));
      const emp = c.bump(p, 1.6 / D, 1.7 / D) + c.bump(p, 1.76 / D, 1.86 / D);
      o('wristL', 'rz', -0.3 * emp); o('wristR', 'rz', 0.3 * emp);
      /* in the air the paws come up and forward; back to the chest on landing */
      o('shoulderL', 'rx', -0.7 * hop); o('shoulderR', 'rx', -0.7 * hop); o('elbowL', 'rx', -0.2 * hop); o('elbowR', 'rx', -0.2 * hop);
      o('tail4', 'rx', 0.09 * c.bump(p, 2.1 / D, 2.19 / D));
      o('ctl', 'lid', c.bump(p, 2.0 / D, 2.1 / D));
      o('ctl', 'look', 1 - c.ramp(p, 1.85 / D, 2.0 / D));
    } },
  };
  K.finish(R);
  K.restTurn(R, 'head', [0, HEAD_REST, 0]);      /* bound straight, rests turned a little toward the reader: the neck bends into the turn */
  return R;
}

export default {
  id: 'chipmunk',
  name: 'Eastern chipmunk',
  latin: 'Tamias striatus',
  rests: 'floor',
  build: (THREE, kit) => buildChipmunk(THREE, kit),
  update: (rig, dt, state) => rig.kit.update(rig, dt, state),
  play: (rig, clip, variant) => rig.kit.play(rig, clip, variant),
  rest: (rig) => rig.kit.rest(rig),
};
