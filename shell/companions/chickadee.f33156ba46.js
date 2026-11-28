/*
  The Civic Archive companion: the black-capped chickadee (Poecile atricapillus). It perches on a branch under the
  top bar at the right edge. The dock draws that branch; the companion also carries a sculpted one (rig.perch, hidden
  unless a page sets rig.perch.visible = true) that runs off the right side of the frame.

  Built on the companions' realism kit (kit.js) from research/chickadee.md: no licensed model worth building on was
  found, so the bird is sculpted in code from the measured animal. One unit is its standing height on the perch (about
  60 mm), so the head is 0.4 across, the bill 0.12 proud of the feathers, the tail 0.86 long (0.95 of the wing chord)
  and the visible leg 0.25. Body, neck and head are one signed distance field surfaced as one mesh that bends over a
  skeleton, so the big round head turns on no visible neck; the plumage is painted per vertex from the species sheet
  (black cap down just past the eye, black bib with a ragged lower edge, white cheeks widening backward, grey back,
  buff flanks, white belly) and dressed in soft feather shells, longer on the flanks and belly, sleek on the cap. The
  folded wings carry a stack of eight primaries that fan open from the wrist; the tail is twelve feathers on six bones
  that fan to sixty degrees on landing. The eyes are black in a black cap, so what reads is the wet glint, as on the
  bird. Motion follows the research's numbers: the head moves in 15 to 50 ms snaps and holds, blinks ride on the snaps,
  the whole body swells with 1.3 Hz breathing, hops crouch for 80 ms, push for 60, fly, land in one frame and settle at
  2 Hz, and the species habits are here: the single wing-flick, the tail flick, head cocks, hammering a seed, the bill
  wipe, the rouse, and peering under the branch. Nothing is loaded from anywhere.

  export default { id, name, latin, rests, build(THREE, kit) -> rig, update(rig, dt, state), play(rig, clip) -> seconds, rest(rig) }
    rig.root   1 unit = the bird's height, facing +z toward the viewer, feet at y = 0 on top of the branch
    rig.frame  the box, in root units, a camera should keep in view: { x: [min, max], y: [min, max] }
    rig.perch  a sculpted branch, fixed in place while the bird moves; hidden until a page shows it
    clips      arrive (it lands), idleA, idleB (four fidgets), notice, react, talk, lookLeft, lookRight, rest, dance;
               every clip ends exactly on the rest pose
*/

function buildChickadee(THREE, K) {
  if (!K || !K.rig) throw new Error('the chickadee needs the companions kit: build(THREE, kit)');
  const { sd, surf, rgb, mixc, fbm, sst, lerp, clamp, unit, cross, dot, lin, PI, TAU, HELP } = K;
  const R = K.rig({
    id: 'chickadee', yaw: -0.85, frame: { x: [-0.5, 0.64], y: [-0.19, 1.06] }, fov: 34,
    breath: 1.3, blinkSpeed: 0.45, look: { yaw: 1.5, pitch: 0.6, snap: true },
    idles: ['idleA', 'idleB', 'idleB', 'idleB', 'lookLeft', 'lookRight', 'notice'],
  });
  const V = (a) => new THREE.Vector3(a[0], a[1], a[2]);
  const basis = (xv, yv, zv) => new THREE.Matrix4().makeBasis(V(xv), V(yv), V(zv));
  const eulerOf = (m) => { const e = new THREE.Euler().setFromRotationMatrix(m, 'XYZ'); return [e.x, e.y, e.z]; };

  /* ---------- colours from the species sheet (black, white, greys, buff; never red or blue) ---------- */
  const CAP = rgb(0x0c0c0c), CAP2 = rgb(0x1b1b1b), BIB = rgb(0x0b0b0b), BIB2 = rgb(0x242322);
  const CHEEK = rgb(0xf8f7f3), CHEEK2 = rgb(0xe7e5de);
  const BACK = rgb(0x8d8d87), BACK2 = rgb(0x73736d), MANTLE = rgb(0x9c9c95);
  const WING = rgb(0x67696b), WING2 = rgb(0x4d4f51), EDGE = rgb(0xf1f0ea), COVERT = rgb(0x7b7c79);
  const FLANK = rgb(0xdcc19a), FLANK2 = rgb(0xc5a575), BELLY = rgb(0xf4f2eb), BELLY2 = rgb(0xe9e5da);
  const BILL = rgb(0x141312), BILL2 = rgb(0x2f2b28), LEG = rgb(0x403f3e), LEG2 = rgb(0x5c5a58), CLAW = rgb(0x1c1a19);
  const BARK = rgb(0x6f6154), BARK2 = rgb(0x4d4238), BARK3 = rgb(0x90847a), BARK4 = rgb(0xa9a79f);

  /* ---------- the body: trunk, breast, belly, rump, the big round head and the nape as one smooth shape ---------- */
  const HC = [0, 0.78, 0.17];
  const bodyE = sd.egg([0, 0.4, -0.03], [0.25, 0.29, 0.35], [-0.5, 0, 0]);      /* the long axis points up 29 degrees */
  const breast = sd.egg([0, 0.41, 0.13], [0.22, 0.23, 0.21]);
  const belly = sd.egg([0, 0.31, 0.0], [0.235, 0.215, 0.27]);
  const rump = sd.egg([0, 0.27, -0.29], [0.155, 0.13, 0.165]);
  const head = sd.egg(HC, [0.2, 0.21, 0.22]);
  const nape = sd.egg([0, 0.655, 0.02], [0.165, 0.135, 0.17]);
  const trunk = sd.add(0.06, bodyE, breast, belly, rump);
  const full = sd.add(0.075, trunk, sd.add(0.09, head, nape));

  /* the bill: short, straight, conical, black; the lower mandible is its own part on a jaw joint */
  const JAW = [0, 0.731, 0.315];
  const upperB = sd.add(0.006, sd.limb([0, 0.758, 0.3], [0, 0.731, 0.49], 0.042, 0.0045), sd.limb([0, 0.75, 0.31], [0, 0.733, 0.483], 0.031, 0.003));
  const lowerB = sd.limb([0, 0.735, 0.3], [0, 0.722, 0.482], 0.032, 0.003);

  /* the folded wings: coverts and secondaries lie flat along the upper sides, from the shoulder back toward the rump;
     a flattened chain, turned in at the top so it hugs the back */
  const SH = (s) => [s * 0.19, 0.6, 0.08];                        /* the shoulder */
  const WRIST = (s) => [s * 0.235, 0.5, -0.06];                   /* the wrist, where the primaries fan from */
  const wingS = (s) => sd.xf(sd.chain([[0, 0.15, 0.2], [0, 0.08, 0.04], [0, -0.04, -0.1], [0, -0.15, -0.22]], [0.085, 0.1, 0.08, 0.05], 0.035), [s * 0.232, 0.48, -0.12], [0, 0, s * 0.26], [0.34, 1, 1]);
  const WL = wingS(1), WR = wingS(-1);

  /* legs and feet: the tarsus comes down from an ankle hidden in the belly feathers; three toes forward over the
     front of the branch, one back under it, each with a claw */
  const foot = (s) => {
    const x = s * 0.085, P = [x, 0.02, 0.0];
    const tarsus = sd.limb([x * 0.95, 0.28, -0.065], P, 0.021, 0.016);
    const toes = [], claws = [];
    for (const a of [-0.55, 0, 0.5]) {
      const dx = Math.sin(a) * 0.075, mid = [x + dx * 0.6, 0.01, 0.07], tip = [x + dx, -0.075, 0.092];
      toes.push(sd.chain([P, mid, tip], [0.013, 0.011, 0.008], 0.008));
      claws.push(sd.limb(tip, [x + dx * 1.1, -0.112, 0.1], 0.005, 0.0015));
    }
    toes.push(sd.chain([P, [x, 0.0, -0.06], [x, -0.07, -0.086]], [0.013, 0.011, 0.008], 0.008));
    claws.push(sd.limb([x, -0.07, -0.086], [x, -0.112, -0.092], 0.005, 0.0015));
    const clawS = sd.add(0, ...claws);
    return { f: sd.add(0.01, tarsus, sd.add(0.008, ...toes), clawS), claw: clawS };
  };
  const FtL = foot(1), FtR = foot(-1);

  /* the branch: runs off to the right, tapers to a tip on the left, a twig and a knot; bumpy bark */
  const branchMain = sd.chain([[1.15, -0.09, -0.02], [0.55, -0.085, -0.005], [0.0, -0.082, 0.0], [-0.3, -0.075, 0.012], [-0.52, -0.06, 0.03]], [0.088, 0.084, 0.08, 0.055, 0.018], 0.02);
  const twig = sd.add(0.012, sd.limb([-0.28, -0.065, 0.0], [-0.44, 0.07, 0.05], 0.018, 0.007), sd.ball([-0.445, 0.08, 0.052], 0.013));
  const branchSmooth = sd.add(0.02, branchMain, twig, sd.ball([0.34, -0.045, 0.05], 0.024));
  const branchS = (() => { const f = (x, y, z) => branchSmooth(x, y, z) + 0.0035 * (fbm(x * 6, y * 42, z * 42, 2) - 0.5); f.b = branchSmooth.b; return f; })();

  /* everything together shades the crevices (the wing against the body, the head on the shoulders, the toes on the bark) */
  const all = sd.min(full, upperB, lowerB, WL, WR, FtL.f, FtR.f, branchS);

  /* ---------- the eyes sit in the black cap, looking sideways; found before the paint and the groom ---------- */
  const EYES = [];
  for (const s of [1, -1]) {
    const yaw = s * 1.05, pit = 0.0;
    const d = [Math.sin(yaw) * Math.cos(pit), Math.sin(pit), Math.cos(yaw) * Math.cos(pit)];
    EYES.push({ s, d, sp: K.hit(full, HC, d) });
  }

  /* ---------- plumage ---------- */
  const plumage = (x, y, z) => {
    const n = fbm(x * 44, y * 44, z * 44, 2), n2 = fbm(x * 11 + 3, y * 11, z * 11, 2) - 0.5, n3 = fbm(x * 19 + 7, y * 19, z * 19, 2) - 0.5;
    const vx = x - HC[0], vy = y - HC[1], vz = z - HC[2], r = Math.hypot(vx, vy, vz) || 1e-6;
    const el = Math.asin(clamp(vy / r, -1, 1)), az = Math.abs(Math.atan2(vx, vz));      /* around the head: 0 forward, PI back */
    const phi = Math.abs(Math.atan2(x, z - 0.02));                                       /* around the body: 0 front, PI back */
    const headK = sst(0.56, 0.66, y);
    /* the cap: over the crown, down to just under the eye on the sides, rising at the back where the white cheeks wrap
       round; a black band runs down the middle of the nape to the grey back */
    const capLine = -0.2 + 0.44 * sst(1.75, 2.75, az);
    let cap = sst(-0.03, 0.03, el - capLine + 0.03 * n2) * sst(0.5, 0.58, y);
    const napeBand = sst(0.1, 0.06, Math.abs(x) + 0.35 * Math.max(0, 0.68 - y)) * sst(-0.02, -0.1, z) * sst(0.5, 0.58, y) * (1 - sst(0.78, 0.84, y));
    cap = Math.max(cap, napeBand);
    /* the bib: chin and throat to the upper breast, with a ragged lower edge; on the head it stops at the jaw line,
       under the white cheek */
    const jawLine = -0.27 - 0.52 * sst(0.3, 1.9, az);
    const bibHead = sst(0.03, -0.03, el - jawLine + 0.03 * n2) * sst(2.1, 1.7, az);
    const bibHalf = 0.95 - 0.45 * sst(0.6, 0.46, y);
    const bibBottom = 0.485 + 0.05 * n2 + 0.035 * n3 - 0.04 * (1 - sst(0.3, 0.9, phi));
    const bibBody = sst(0.06, -0.06, phi - bibHalf + 0.08 * n2) * sst(bibBottom - 0.015, bibBottom + 0.015, y) * sst(0.7, 0.62, y);
    const bib = lerp(bibBody, bibHead, headK);
    /* the body: white breast and belly, buff flanks under the wings, soft grey back, a shade lighter at the mantle */
    const back = sst(1.5, 1.9, phi) * sst(0.68, 0.6, y);
    const flank = sst(0.65, 1.1, phi) * (1 - sst(1.5, 1.8, phi)) * sst(0.5, 0.36, y) * sst(0.1, 0.22, y);
    let c = mixc(BELLY, BELLY2, 0.3 * n + 0.3 * sst(0.3, 0.12, y));
    c = mixc(c, mixc(FLANK, FLANK2, n), flank * (0.75 + 0.25 * n));
    c = mixc(c, mixc(BACK, BACK2, n), back);
    c = mixc(c, MANTLE, back * sst(0.5, 0.62, y) * 0.5);
    /* the head: white cheeks, except at the bill, where lores and chin are black */
    const cheekC = mixc(CHEEK, CHEEK2, 0.5 * n);
    const atBill = 1 - sst(0.12, 0.24, az);
    c = mixc(c, cheekC, headK * (1 - atBill));
    c = mixc(c, mixc(CAP, CAP2, n * 0.8), Math.max(cap, headK * atBill));
    c = mixc(c, mixc(BIB, BIB2, n * 0.9), bib);
    return c;
  };
  /* the cap and bib are glossier than the soft body feathers */
  const matAt = (x, y, z) => {
    const vx = x - HC[0], vy = y - HC[1], vz = z - HC[2], r = Math.hypot(vx, vy, vz) || 1e-6;
    const el = Math.asin(clamp(vy / r, -1, 1));
    const capK = sst(-0.25, -0.15, el) * sst(0.56, 0.66, y);
    return [1 - 0.15 * capK, 1 + 1.4 * capK, 1 - 0.25 * capK];
  };
  /* the groom: soft feathers lying back along the body and down; longest on the flanks and belly (the bird is a
     fluffy ball), short and sleek on the cap, none across the eyes or the base of the bill */
  const groom = (x, y, z) => {
    const headK = sst(0.6, 0.7, y), phi = Math.abs(Math.atan2(x, z - 0.02));
    const flank = sst(0.6, 1.2, phi) * (1 - sst(1.7, 2.0, phi)) * (1 - headK);
    const belly = (1 - sst(0.9, 1.4, phi)) * sst(0.5, 0.25, y);
    let len = lerp(1.0, 0.5, headK) * (0.85 + 0.45 * flank + 0.35 * belly + 0.25 * sst(0.4, 0.2, y));
    for (const E of EYES) len *= sst(0.035, 0.075, Math.hypot(x - E.sp[0], y - E.sp[1], z - E.sp[2]));
    len *= sst(0.06, 0.13, Math.hypot(x, y - 0.74, z - 0.34));
    return [len, 1, -0.25 * x, -0.75 + 0.3 * headK, -0.6 - 0.2 * headK];
  };

  /* ---------- materials ---------- */
  const feather = K.physical({ rough: 0.62, sheen: 0.55, sheenRough: 0.5, spec: 0.45, clearcoat: 0.12, ccRough: 0.4, name: 'chickadee-feather' });
  const wingM = (n) => K.physical({ rough: 0.52, sheen: 0.35, sheenRough: 0.45, spec: 0.5, clearcoat: 0.1, ccRough: 0.3, name: 'chickadee-wing-' + n });
  const vaneM = (n) => K.physical({ rough: 0.5, sheen: 0.3, sheenRough: 0.4, spec: 0.5, clearcoat: 0.12, ccRough: 0.25, side: THREE.DoubleSide, name: 'chickadee-vane-' + n });
  const horn = (n) => K.physical({ rough: 0.3, clearcoat: 0.7, ccRough: 0.15, spec: 0.75, name: 'chickadee-bill-' + n });
  const skinM = (n) => K.physical({ rough: 0.66, clearcoat: 0.12, ccRough: 0.45, sheen: 0.1, spec: 0.45, name: 'chickadee-leg-' + n });
  const barkM = K.physical({ rough: 0.92, spec: 0.25, name: 'chickadee-bark' });

  /* ---------- joints ---------- */
  /* a fixed frame under the root for the branch: it never moves with the bird */
  const ground = new THREE.Bone(); ground.name = 'ground'; R.root.add(ground); R.j.ground = ground; R.piv.ground = [0, 0, 0];
  K.joint(R, 'perch', 'ground', [0, -0.082, 0]);
  K.joint(R, 'body', 'pose', [0, 0.3, -0.02]);
  K.joint(R, 'neck', 'body', [0, 0.57, 0.08]);
  K.joint(R, 'head', 'neck', [0, 0.64, 0.15]);
  K.joint(R, 'jaw', 'head', JAW);
  K.joint(R, 'footL', 'pose', [0.085, 0.02, 0.0]);
  K.joint(R, 'footR', 'pose', [-0.085, 0.02, 0.0]);
  K.limit(R, 'head', { ry: [-2.2, 2.2], rx: [-1.3, 1.3], rz: [-1.2, 1.2] });

  /* the tail: twelve feathers on six fan bones; the tail bone lifts and swings the whole */
  const TB = [0, 0.265, -0.4];
  const xT = unit([0, -0.42, -0.91]), zT = unit([0, 0.91, -0.42]), yT = cross(zT, xT);
  const MT = basis(xT, yT, zT), ET = eulerOf(MT);
  K.joint(R, 'tail', 'body', TB);
  for (const s of [1, -1]) for (let k = 0; k < 3; k++) K.joint(R, 'tf' + (s > 0 ? 'L' : 'R') + k, 'tail', TB, ET);
  const TAIL_FAN = [0.12, 0.3, 0.5];

  /* the wings: a shoulder joint that opens and flaps; a hand joint at the wrist whose frame runs along the leading
     primary (x), across the fan toward the trailing edge (y) and out of the wing (z); three fan bones under it */
  const HAND = {}, Q_OPEN = {};
  for (const s of [1, -1]) {
    const side = s > 0 ? 'L' : 'R';
    K.joint(R, 'wing' + side, 'body', SH(s));
    const tip = [s * 0.09, 0.25, -0.62], W = WRIST(s);
    const xh = unit([tip[0] - W[0], tip[1] - W[1], tip[2] - W[2]]);
    const zh = unit(cross([0, -1, 0], xh).map((v) => v * s));
    const yh = cross(zh, xh);
    const M = basis(xh, yh, zh);
    /* in the folded hand the leading edge (the longest, outermost primary) is the lower edge of the stack, and the
       inner primaries fan up and back from it toward the tertials; open, that is the trailing edge */
    HAND[side] = { M: M.clone().setPosition(W[0], W[1], W[2]), spread: s, len: Math.hypot(tip[0] - W[0], tip[1] - W[1], tip[2] - W[2]) };
    K.joint(R, 'hand' + side, 'wing' + side, W, eulerOf(M));
    for (let k = 0; k < 3; k++) K.joint(R, 'pf' + side + k, 'hand' + side, W);
    /* the open wing: from folded (back and down along the side, dorsal face out) to spread (out to the side, a little
       up and forward, dorsal face up, leading edge forward) */
    const d0 = unit([0, -0.56, -0.83]), n0 = [s, 0, 0], c0 = cross(d0, n0).map((v) => v * s);
    const d1 = unit([s * 0.9, 0.3, 0.3]); let n1 = [0, 1, 0]; const kk = dot(n1, d1); n1 = unit([n1[0] - kk * d1[0], n1[1] - kk * d1[1], n1[2] - kk * d1[2]]);
    const c1 = cross(d1, n1).map((v) => v * s);
    const F0 = basis(d0, n0, c0), F1 = basis(d1, n1, c1);
    Q_OPEN[side] = new THREE.Quaternion().setFromRotationMatrix(F1.multiply(F0.clone().transpose()));
  }
  const WING_FAN = [0.12, 0.38, 0.62];

  /* ---------- flat feathers: tapered slabs along x in a frame, turned by an angle about z, stacked a hair apart ---------- */
  function vanes(list, M, paint, o = {}) {
    const P = [], N = [], C = [], A = [], SI = [], SW = [], idx = [], segs = o.segs || 6, rows = 3, v3 = new THREE.Vector3();
    list.forEach((f, i) => {
      const base = P.length / 3, ca = Math.cos(f.ang), sa = Math.sin(f.ang);
      for (let k = 0; k <= segs; k++) {
        const u = k / segs, L = f.len * u;
        const half = f.w * (0.3 + 0.7 * Math.pow(Math.sin(Math.min(1, u * 1.12) * PI), 0.7)) * Math.min(1, u / 0.06 + 0.15);
        const curl = (f.curl || 0) * u * u;
        for (let r2 = 0; r2 < rows; r2++) {
          const v = r2 - 1, across = v * half * (v < 0 ? (f.lead == null ? 0.55 : f.lead) : 1);
          v3.set(L * ca - across * sa, L * sa + across * ca, f.z + curl).applyMatrix4(M);
          P.push(v3.x, v3.y, v3.z);
          v3.set(0, 0, 1).transformDirection(M); N.push(v3.x, v3.y, v3.z);
          const c = paint(i, u, v); C.push(lin(c[0]), lin(c[1]), lin(c[2])); A.push(1);
          if (o.bones) { SI.push(o.bones[i], 0, 0, 0); SW.push(1, 0, 0, 0); }
        }
      }
      for (let k = 0; k < segs; k++) for (let r2 = 0; r2 < rows - 1; r2++) {
        const a = base + k * rows + r2, b = a + rows;
        idx.push(a, b, a + 1, a + 1, b, b + 1);
      }
    });
    const g = new THREE.BufferGeometry();
    g.setAttribute('position', new THREE.Float32BufferAttribute(P, 3));
    g.setAttribute('normal', new THREE.Float32BufferAttribute(N, 3));
    g.setAttribute('color', new THREE.Float32BufferAttribute(C, 3));
    g.setAttribute('ao', new THREE.Float32BufferAttribute(A, 1));
    if (o.bones) { g.setAttribute('skinIndex', new THREE.Uint16BufferAttribute(SI, 4)); g.setAttribute('skinWeight', new THREE.Float32BufferAttribute(SW, 4)); }
    g.setIndex(idx);
    return g;
  }
  /* a mesh whose skin weights were written by hand (one bone per feather) hangs under the pose and is bound in finish() */
  function skinned(geo, boneNames, material, name) {
    K.tune(material, geo);
    const m = new THREE.SkinnedMesh(geo, material);
    m.name = name + '-mesh'; m.frustumCulled = false; m.castShadow = true; m.receiveShadow = true;
    R.j.pose.add(m); R.geos.push(geo); R.mats.add(material);
    R.skins.push({ mesh: m, bones: boneNames.map((n) => R.j[n]), extra: [] });
    return m;
  }

  /* ---------- meshes ---------- */
  /* the skinned body: the body bone never reaches the face, the head bone never the chest; the neck bridges them */
  const bodyGeo = surf(full, [-0.3, 0.05, -0.5, 0.3, 1.03, 0.43], 0.009, plumage, { ao: all, groom, matAt });
  const bodyMesh = K.skin(R, bodyGeo, [
    { j: 'body', a: [0, 0.22, -0.1], b: [0, 0.54, 0.12], r: 0.3, only: (x, y) => sst(0.66, 0.56, y) },
    { j: 'neck', a: [0, 0.56, 0.08], b: [0, 0.65, 0.15], r: 0.17, only: (x, y) => sst(0.48, 0.56, y) * sst(0.74, 0.66, y) },
    { j: 'head', a: [0, 0.66, 0.16], b: [0, 0.95, 0.19], r: 0.26, only: (x, y) => sst(0.56, 0.64, y) },
  ], feather, { smooth: 3, name: 'chickadee-body' });
  K.fur(R, bodyMesh, { len: 0.016, dens: 165, thin: 0.9, root: 0.78, clump: 0.45, comb: 0.7, droop: 0.12, min: 0.45 });

  /* the bill */
  const paintBill = (x, y, z) => mixc(BILL, BILL2, sst(0.4, 0.49, z) * 0.5 + 0.2 * fbm(x * 90, y * 90, z * 90, 2));
  K.put(R, 'head', surf(upperB, [-0.05, 0.7, 0.27, 0.05, 0.81, 0.51], 0.0038, paintBill, { ao: all }), horn('upper'));
  K.put(R, 'jaw', surf(lowerB, [-0.045, 0.69, 0.27, 0.045, 0.78, 0.5], 0.0038, paintBill, { ao: all }), horn('lower'));

  /* the folded wings: slate coverts shading into the back's grey at the top; the secondaries and tertials show their
     white edges as pale streaks toward the trailing edge */
  const paintWing = (s) => (x, y, z) => {
    const n = fbm(x * 40, y * 40, z * 40, 2);
    const u = clamp((0.64 - y) / 0.34, 0, 1);                                      /* shoulder (0) to the rear (1) */
    const top = s * (x - s * 0.232) + 0.26 * (y - 0.48);                           /* out of the body: the exposed face */
    const v = clamp((0.64 - y) * 1.1 - (z + 0.1 + 0.3 * (0.64 - y)) * 0.9 + 0.3, 0, 1);  /* upper edge (0) to the trailing edge (1) */
    const streak = sst(0.74, 0.9, 0.5 + 0.5 * Math.sin(u * TAU * 6.5 + v * 2.0 + n * 0.8)) * sst(0.4, 0.65, v) * sst(0.1, 0.3, u) * (1 - sst(0.85, 0.97, u)) * (0.6 + 0.4 * sst(0.45, 0.75, u));
    let c = mixc(WING, WING2, n * 0.6 + 0.3 * u);
    c = mixc(c, COVERT, (1 - sst(0.2, 0.45, v)) * 0.6);
    c = mixc(c, EDGE, Math.max(0.75 * streak, 0.6 * sst(0.9, 1.0, v) * sst(0.15, 0.4, u)));
    return mixc(c, mixc(BACK, MANTLE, 0.4), (1 - sst(0.05, 0.22, u)) * (1 - sst(0.1, 0.35, v)) * 0.7 * sst(-0.02, 0.03, top));
  };
  K.put(R, 'wingL', surf(WL, [0.09, 0.2, -0.42, 0.33, 0.74, 0.3], 0.0066, paintWing(1), { ao: all }), wingM('l'));
  K.put(R, 'wingR', surf(WR, [-0.33, 0.2, -0.42, -0.09, 0.74, 0.3], 0.0066, paintWing(-1), { ao: all }), wingM('r'));

  /* the primaries: eight per wing, stacked at the wrist, the innermost on top; they fan toward the trailing edge */
  for (const s of [1, -1]) {
    const side = s > 0 ? 'L' : 'R', H = HAND[side], list = [], bones = [];
    for (let i = 0; i < 8; i++) {
      list.push({ ang: H.spread * i * 0.023, len: H.len * (1 - 0.035 * i), w: 0.046, z: -0.018 + i * 0.0045, lead: 0.5, curl: 0.02 * s });
      bones.push(Math.min(2, Math.floor(i * 3 / 8)));
    }
    const paint = (i, u, v) => {
      const n = fbm(i * 3.1, u * 9, v * 2, 2);
      let c = mixc(WING2, WING, 0.5 * n + 0.2 * (1 - u));
      c = mixc(c, EDGE, 0.28 * sst(0.3, 1.0, -v) * (1 - sst(0.8, 1.0, u)) * sst(0.2, 0.5, u));
      return mixc(c, CAP2, 0.4 * (1 - Math.abs(v)) * (1 - sst(0.9, 1, u)));
    };
    skinned(vanes(list, H.M, paint, { bones: bones.map((k) => k) }), [0, 1, 2].map((k) => 'pf' + side + k), vaneM('wing-' + side), 'chickadee-primaries-' + side);
  }

  /* the tail: six pairs; the central pair on top, the outer pairs lowest, their outer webs edged pale */
  {
    const list = [], bones = [], names = ['tfL0', 'tfL1', 'tfL2', 'tfR0', 'tfR1', 'tfR2'];
    for (const s of [1, -1]) for (let j = 0; j < 6; j++) {
      list.push({ ang: -s * (0.02 + 0.016 * j), len: 0.86 - 0.012 * j, w: 0.044, z: 0.012 - j * 0.0042, lead: s > 0 ? 1 : 0.55, curl: -0.02 });
      bones.push((s > 0 ? 0 : 3) + Math.floor(j / 2));
    }
    const paint = (i, u, v) => {
      const s = i < 6 ? 1 : -1, j = i % 6, n = fbm(i * 2.3, u * 8, v * 2, 2);
      const outer = s > 0 ? v : -v;                                                /* the web that faces away from the centre */
      let c = mixc(WING2, WING, 0.5 * n + 0.25 * u);
      c = mixc(c, EDGE, (j >= 4 ? 0.75 : j === 3 ? 0.35 : 0.1) * sst(0.2, 0.9, outer) * (1 - sst(0.9, 1.0, u)) * sst(0.08, 0.2, u));
      return mixc(c, CAP2, 0.45 * (1 - Math.abs(v)) * (1 - sst(0.9, 1, u)));
    };
    const MTB = MT.clone().setPosition(TB[0], TB[1], TB[2]);
    skinned(vanes(list, MTB, paint, { bones, segs: 7 }), names, vaneM('tail'), 'chickadee-tail');
  }

  /* the feet */
  const paintFoot = (Ft) => (x, y, z) => {
    if (Ft.claw(x, y, z) < 0.004) return CLAW;
    return mixc(LEG, LEG2, 0.3 + 0.5 * fbm(x * 70, y * 70, z * 70, 2) * sst(0.0, 0.05, y));
  };
  K.put(R, 'footL', surf(FtL.f, [0.0, -0.13, -0.11, 0.19, 0.3, 0.13], 0.006, paintFoot(FtL), { ao: all }), skinM('l'));
  K.put(R, 'footR', surf(FtR.f, [-0.19, -0.13, -0.11, 0.0, 0.3, 0.13], 0.006, paintFoot(FtR), { ao: all }), skinM('r'));

  /* the branch, hidden until a page shows it */
  const paintBark = (x, y, z) => {
    const n = fbm(x * 7, y * 45, z * 45, 3), m = fbm(x * 20 + 3, y * 20, z * 20, 2), l = fbm(x * 14 + 9, y * 30, z * 30, 2);
    let c = mixc(BARK, BARK2, sst(0.45, 0.75, n));
    c = mixc(c, BARK3, 0.5 * sst(0.6, 0.8, m));
    c = mixc(c, BARK4, 0.45 * sst(0.66, 0.78, l) * sst(-0.06, 0.02, y));
    return x < -0.3 && y > 0 ? mixc(c, rgb(0x7f6c55), 0.5) : c;
  };
  const perchMesh = K.put(R, 'perch', surf(branchS, [-0.58, -0.2, -0.13, 1.26, 0.12, 0.12], 0.015, paintBark, { ao: all }), barkM);
  perchMesh.visible = false;
  R.perch = perchMesh;

  /* the eyes: black in a black cap; what reads is the wet glint. The lids are cap-coloured */
  for (const E of EYES) {
    const { s, d, sp } = E, r = 0.03, c = [sp[0] - d[0] * r * 0.45, sp[1] - d[1] * r * 0.45, sp[2] - d[2] * r * 0.45];
    const name = s > 0 ? 'eyeL' : 'eyeR';
    K.eye(R, name, 'head', c, d, r, { iris: 0x120c08, iris2: 0x20140b, pupil: 0.55, irisAngle: 1.0, sclera: 0x17120e, limbal: 0x060403,
      lid: CAP, lidMat: { rough: 0.62, sheen: 0.4, clearcoat: 0.15, name: name + '-lid' }, open: -0.9, shut: 1.5, lidScale: 1.1, lowerShare: 0.35, glint: 0.34, gloss: 0.75, wet: 0.5 });
  }

  /* secondary motion: the tail swings after a hop or a turn and follows a flick through */
  K.spring(R, 'tail', { ch: 'rx', k: 420, c: 21, gain: 0.045, dir: [0, -0.42, -0.91], lim: [-0.3, 0.3] });

  /* ---------- the wings' control: one call opens, flaps and sweeps a wing and fans its primaries ---------- */
  const qT = new THREE.Quaternion(), qI = new THREE.Quaternion(), qR = new THREE.Quaternion(), eT = new THREE.Euler(), Z = new THREE.Vector3(0, 0, 1), Y = new THREE.Vector3(0, 1, 0);
  function wing(o, s, open, flap = 0, sweep = 0) {
    const side = s > 0 ? 'L' : 'R', op = clamp(open, 0, 1);
    qT.copy(qI).slerp(Q_OPEN[side], op);
    if (flap) { qR.setFromAxisAngle(Z, s * flap); qT.premultiply(qR); }
    if (sweep) { qR.setFromAxisAngle(Y, -s * sweep); qT.premultiply(qR); }
    eT.setFromQuaternion(qT, 'XYZ');
    o('wing' + side, 'rx', eT.x); o('wing' + side, 'ry', eT.y); o('wing' + side, 'rz', eT.z);
    for (let k = 0; k < 3; k++) o('pf' + side + k, 'rz', s * op * WING_FAN[k]);
  }
  const wings = (o, open, flap = 0, sweep = 0) => { wing(o, 1, open, flap, sweep); wing(o, -1, open, flap, sweep); };
  const fan = (o, a) => { for (let k = 0; k < 3; k++) { o('tfL' + k, 'rz', -a * TAIL_FAN[k]); o('tfR' + k, 'rz', a * TAIL_FAN[k]); } };
  const tail = (o, lift, swing = 0) => { o('tail', 'rx', lift); if (swing) o('tail', 'ry', swing); };

  /* ---------- breathing, attention, ducking ---------- */
  R.spec.life = (o, L) => {
    const b = L.b;
    o('body', 's', 0.022 * b); o('body', 'sy', 0.006 * b);
    o('head', 'py', 0.004 * b); o('neck', 'py', 0.002 * b);
    o('tail', 'rx', 0.02 * b);
    o('head', 'ry', L.yaw); o('head', 'rx', 0.7 * L.pitch); o('head', 'rz', -0.3 * L.yaw);
    o('neck', 'ry', 0.15 * L.yaw);
  };
  R.spec.duck = (o, d) => { o('mover', 'px', 0.3 * d); o('pose', 'ry', 0.55 * d); o('body', 'rx', 0.12 * d); o('head', 'rx', -0.1 * d); o('body', 's', -0.02 * d); };

  /* ---------- clips: t in seconds; every helper is exactly zero outside its own span ---------- */
  const step = (t, a, w = 0.02) => sst(a, a + w, t);
  const hold = (t, a, b, w = 0.02) => sst(a, a + w, t) * (1 - sst(b - w, b, t));
  const bump = (t, a, b) => HELP.bump(t, a, b);
  const ring = (t, a, b, f, d) => (t <= a || t >= b ? 0 : Math.sin(TAU * f * (t - a)) * Math.exp(-d * (t - a)) * (1 - sst(b - 0.1, b, t)));
  const osc = (t, a, b, f, ph = 0) => (t <= a || t >= b ? 0 : Math.sin(TAU * f * (t - a) + ph) * sst(a, a + 0.04, t) * (1 - sst(b - 0.04, b, t)));
  const blink = (o, t, a, w = 0.12) => o('ctl', 'lid', bump(t, a - 0.01, a + w));
  /* the hop: crouch 80 ms, push 60, air, land in 12 ms, settle at 2 Hz. The feet stay on the branch until lift-off and
     tuck in the air; the tail dips in the crouch and lifts and fans on landing; the branch dips with the landing */
  function hop(o, t, t0, h = 0.22, air = 0.15) {
    const c1 = t0 + 0.08, p1 = c1 + 0.06, a1 = p1 + air, s1 = a1 + 0.36;
    if (t <= t0 || t >= s1) return;
    const cr = sst(t0, c1, t) * (1 - sst(c1, p1, t));
    o('body', 'py', -0.085 * cr); o('body', 'rx', 0.18 * cr); o('head', 'rx', -0.18 * cr); o('body', 's', -0.03 * cr);
    tail(o, -0.26 * cr);
    const push = sst(c1, p1, t) * (1 - sst(p1, p1 + 0.05, t));
    o('body', 'py', 0.03 * push); o('neck', 'py', 0.02 * push);
    const fl = t > p1 && t < a1 ? (t - p1) / air : 0, up = fl > 0 ? 4 * fl * (1 - fl) : 0;
    o('mover', 'py', h * up);
    o('footL', 'rx', 0.55 * up); o('footR', 'rx', 0.55 * up); o('footL', 'py', 0.025 * up); o('footR', 'py', 0.025 * up);
    o('body', 'rx', -0.1 * up);
    const ab = bump(t, a1 - 0.004, a1 + 0.06);
    o('body', 'py', -0.05 * ab); o('body', 'rx', 0.12 * ab);
    o('body', 'py', 0.03 * ring(t, a1 + 0.012, s1, 2.2, 7));
    const tl = bump(t, a1 - 0.01, a1 + 0.3);
    tail(o, 0.42 * tl); fan(o, 0.6 * tl);
    o('perch', 'py', -0.022 * ring(t, a1, Math.min(s1, a1 + 0.5), 3, 8));
  }
  /* the single wing-flick: one wing lifted and extended, folded again at once (about 220 ms) */
  const flick = (o, s, t, a, amt = 0.65) => { const e = hold(t, a, a + 0.22, 0.08); if (e > 0) wing(o, s, amt * e, 0.25 * e); };
  const FACE = 0.85;                       /* the head turn that faces the camera straight on */

  R.clips = {
    arrive: { dur: 1.7, fn(p, o) { /* bounds in from the upper right, flares steep, lands, settles, and looks at the reader with one eye */
      const t = p * 1.7, fly = 1 - step(t, 0.86, 0.1);
      const q = clamp(t / 0.95, 0, 1), u = 1 - Math.pow(1 - q, 1.25);
      const burst = sst(-0.1, 0.4, Math.cos(TAU * 2 * u)) * fly;
      o('mover', 'px', 1.25 * (1 - u));
      o('mover', 'py', 0.7 * Math.pow(1 - u, 1.5) + 0.09 * Math.sin(TAU * 2 * u) * (1 - u) * fly);
      o('pose', 'ry', -0.7 * (1 - sst(0.55, 0.9, t)));
      const flare = bump(t, 0.7, 1.0);
      const openFly = fly * (0.9 * (0.4 + 0.6 * burst) * (1 - flare) + 0.92 * flare);
      const openPost = 0.92 * (1 - fly) * (1 - 0.55 * step(t, 0.96, 0.1) - 0.45 * step(t, 1.1, 0.12));
      wings(o, openFly + openPost, 0.55 * Math.sin(TAU * 9 * t) * burst * (1 - flare) + 0.28 * Math.sin(TAU * 5 * t) * flare * fly, 0.15 * flare);
      o('body', 'rx', 0.35 * fly * (1 - flare) - 0.5 * flare);
      o('head', 'rx', -0.25 * fly * (1 - flare) + 0.2 * flare);
      o('neck', 'pz', 0.04 * fly);
      tail(o, 0.1 * fly * (1 - flare) + 0.5 * flare); fan(o, 0.85 * flare + 0.8 * (1 - fly) * (1 - step(t, 0.98, 0.25)));
      o('footL', 'pz', 0.07 * flare); o('footR', 'pz', 0.07 * flare); o('footL', 'rx', -0.4 * flare); o('footR', 'rx', -0.4 * flare);
      o('footL', 'py', 0.06 * fly * (1 - flare)); o('footR', 'py', 0.06 * fly * (1 - flare));
      o('footL', 'rx', 0.6 * fly * (1 - flare)); o('footR', 'rx', 0.6 * fly * (1 - flare));
      o('body', 'py', -0.06 * bump(t, 0.93, 1.03) + 0.035 * ring(t, 1.0, 1.45, 2.2, 6));
      o('perch', 'py', -0.03 * ring(t, 0.95, 1.5, 3, 7));
      const look = hold(t, 1.25, 1.52, 0.025);
      o('head', 'ry', 1.55 * look); o('head', 'rz', 0.15 * look);
      blink(o, t, 1.25); blink(o, t, 1.52);
      o('ctl', 'look', 1 - step(t, 1.55, 0.15));
    } },
    idleA: { dur: 4.6, fn(p, o, c) { /* breathing with two blinks, a small weight shift, a glance held, a tail flick */
      const t = p * 4.6, sgn = c.r > 0.5 ? 1 : -1;
      blink(o, t, 1.0 + 1.2 * c.r); blink(o, t, 3.3 - 0.8 * c.r);
      o('body', 'rz', 0.05 * sgn * bump(t, 1.4, 2.6)); o('head', 'rz', -0.04 * sgn * bump(t, 1.4, 2.6));
      o('body', 's', -0.02 * bump(t, 0.5, 3.5)); o('head', 's', -0.012 * bump(t, 0.5, 3.5));
      const g = hold(t, 2.0, 3.2, 0.025);
      o('head', 'ry', 0.35 * sgn * g); o('head', 'rz', 0.12 * sgn * g); blink(o, t, 2.0);
      tail(o, -0.3 * bump(t, 3.9, 4.12)); fan(o, 0.25 * bump(t, 3.9, 4.15));
      o('ctl', 'amp', 0.4 * bump(t, 0.3, 2.0));
      o('ctl', 'look', g);
    } },
    idleB: { variants: 4, dur: (v) => [2.4, 1.7, 3.4, 2.8][v], fn(p, o, c) {
      if (c.v === 0) { /* head cocks: three snaps of roll, one eye up, held between */
        const t = p * 2.4, a = hold(t, 0.1, 0.62, 0.03), b = hold(t, 0.76, 1.5, 0.03), d = hold(t, 1.64, 2.12, 0.03);
        o('head', 'rz', 0.62 * a - 0.55 * b + 0.42 * d); o('head', 'ry', 0.3 * a - 0.2 * b + 0.45 * d); o('head', 'rx', -0.12 * a + 0.08 * b - 0.1 * d);
        for (const s of [0.1, 0.62, 0.76, 1.5, 1.64, 2.12]) blink(o, t, s, 0.1);
        o('ctl', 'look', Math.max(a, b, d));
      } else if (c.v === 1) { /* the single wing-flick, a tail flick, a glance */
        const t = p * 1.7;
        flick(o, 1, t, 0.25);
        tail(o, -0.36 * bump(t, 0.7, 0.92), 0.12 * osc(t, 0.7, 1.0, 3)); fan(o, 0.4 * bump(t, 0.7, 0.95));
        const g = hold(t, 1.05, 1.5, 0.025);
        o('head', 'ry', -0.8 * g); o('head', 'rz', -0.2 * g); blink(o, t, 1.05); blink(o, t, 1.5);
        o('ctl', 'look', g);
      } else if (c.v === 2) { /* hammering a seed held under the toes: pecks in bursts of five and four, a look up between, a bill wipe after */
        const t = p * 3.4, e = hold(t, 0.0, 3.15, 0.28);
        o('body', 'rx', 0.5 * e); o('body', 'py', -0.03 * e); o('head', 'rx', 0.8 * e); o('neck', 'pz', 0.05 * e); o('neck', 'py', -0.02 * e);
        tail(o, 0.25 * e);
        const peck = Math.max(0, Math.sin(TAU * 7 * (t - 0.3))) * (hold(t, 0.3, 1.02, 0.05) + hold(t, 1.62, 2.2, 0.05));
        o('head', 'rx', 0.3 * peck); o('body', 'rx', 0.05 * peck); o('neck', 'pz', 0.015 * peck);
        const up = hold(t, 1.1, 1.55, 0.03);
        o('head', 'rx', -0.95 * up); o('head', 'ry', 0.4 * up); blink(o, t, 1.1); blink(o, t, 1.55);
        o('head', 'rz', 0.5 * bump(t, 2.3, 2.44) - 0.5 * bump(t, 2.47, 2.61)); o('head', 'ry', 0.3 * bump(t, 2.3, 2.44) - 0.3 * bump(t, 2.47, 2.61));
        o('ctl', 'look', e);
      } else { /* peering under the branch: the body tips far forward over the front, the tail balances, the head bends back up to the reader */
        const t = p * 2.8, e = hold(t, 0.05, 2.55, 0.3);
        o('body', 'rx', 0.9 * e); o('body', 'pz', 0.06 * e); o('body', 'py', -0.04 * e);
        tail(o, 0.3 * e); fan(o, 0.15 * e);
        o('head', 'rx', -1.2 * e); o('head', 'ry', 0.9 * e); o('neck', 'pz', 0.06 * e);
        wings(o, 0.12 * e);
        const g = hold(t, 1.4, 2.0, 0.03);
        o('head', 'ry', -0.3 * g); o('head', 'rz', 0.25 * g); blink(o, t, 1.4); blink(o, t, 2.0);
        o('ctl', 'look', e);
      }
    } },
    notice: { variants: 2, dur: 1.25, fn(p, o, c) { /* one snap puts an eye on the reader, the neck extends, held with two small adjustments */
      const t = p * 1.25, e = hold(t, 0.05, 1.02, 0.022);
      if (c.v === 0) { o('head', 'ry', 1.55 * e); o('head', 'rz', 0.12 * e); } else { o('head', 'ry', -0.32 * e); o('head', 'rz', -0.38 * e); }
      o('head', 'ry', 0.08 * hold(t, 0.4, 0.72, 0.03) - 0.06 * hold(t, 0.72, 1.02, 0.03));
      o('neck', 'py', 0.06 * e); o('neck', 'pz', 0.02 * e); o('body', 's', -0.02 * e); o('head', 's', -0.02 * e);
      blink(o, t, 0.05); blink(o, t, 1.02);
      o('ctl', 'look', e);
    } },
    react: { dur: 1.5, fn(p, o) { /* the startle-and-hop: sleek, crouch, leap with a flutter, land, settle; then a wing-flick toward the reader and a head cock */
      const t = p * 1.5, sl = hold(t, 0.0, 0.5, 0.05);
      o('body', 's', -0.035 * sl); o('head', 's', -0.03 * sl); o('neck', 'py', 0.05 * sl);
      hop(o, t, 0.06, 0.3, 0.16);
      const air = hold(t, 0.2, 0.37, 0.03);
      wings(o, 0.7 * air, 0.5 * Math.sin(TAU * 13 * t) * air);
      flick(o, 1, t, 0.78, 0.6);
      const ck = hold(t, 1.02, 1.32, 0.025);
      o('head', 'rz', 0.6 * ck); o('head', 'ry', FACE * ck); blink(o, t, 1.02); blink(o, t, 1.32);
      o('ctl', 'look', hold(t, 0.0, 1.4, 0.05));
    } },
    talk: { dur: 3, fn(p, o) { /* attentive: face to the reader, cocked, small snaps, silent "dee" notes in bursts, the tail dipping with each */
      const t = p * 3, e = hold(t, 0, 3, 0.18);
      o('head', 'ry', FACE * e); o('head', 'rz', 0.35 * e); o('neck', 'py', 0.03 * e);
      o('head', 'ry', 0.2 * hold(t, 0.9, 1.7, 0.03) - 0.15 * hold(t, 1.7, 2.6, 0.03)); o('head', 'rz', -0.15 * hold(t, 1.7, 2.6, 0.03));
      blink(o, t, 0.9); blink(o, t, 1.7); blink(o, t, 2.6);
      const env = hold(t, 0.5, 1.1, 0.05) + hold(t, 1.9, 2.45, 0.05);
      const burst = Math.max(0, Math.sin(TAU * 6 * t)) * env;
      o('jaw', 'rx', 0.32 * burst); o('head', 'rx', -0.05 * burst);
      tail(o, -0.1 * env);
      o('ctl', 'look', e);
    } },
    lookLeft: { dur: 1.05, fn(p, o) { /* one snap to the side, one eye leading, a blink, a hold, the snap back */
      const t = p * 1.05, e = hold(t, 0.05, 0.86, 0.025);
      o('head', 'ry', -1.3 * e); o('head', 'rz', -0.25 * e); o('head', 'rx', 0.05 * e); o('neck', 'ry', -0.1 * e);
      blink(o, t, 0.05); blink(o, t, 0.86);
      o('ctl', 'look', e);
    } },
    lookRight: { dur: 1.05, fn(p, o) {
      const t = p * 1.05, e = hold(t, 0.05, 0.86, 0.025);
      o('head', 'ry', 1.45 * e); o('head', 'rz', 0.25 * e); o('head', 'rx', 0.05 * e); o('neck', 'ry', 0.1 * e);
      blink(o, t, 0.05); blink(o, t, 0.86);
      o('ctl', 'look', e);
    } },
    rest: { dur: 5, fn(p, o) { /* fluffed to a ball, head drawn in and down, lower lids up, slower and deeper breathing, one resettle */
      const t = p * 5, e = hold(t, 0, 5, 1.2);
      o('body', 's', 0.08 * e); o('head', 's', 0.06 * e);
      o('neck', 'py', -0.05 * e); o('neck', 'pz', -0.04 * e); o('head', 'rx', 0.17 * e);
      o('ctl', 'lid', 0.5 * e); o('ctl', 'breath', -0.23 * e); o('ctl', 'amp', 0.4 * e);
      o('body', 's', 0.02 * bump(t, 2.2, 3.4)); o('head', 's', 0.015 * bump(t, 2.2, 3.4));
    } },
    dance: { dur: 2.6, fn(p, o) { /* a branch jig of real moves: hop-pivot right, one eye to the reader, a wing-flick and tail flick,
      hop-pivot round to face away and look back over the shoulder, a bill wipe, a rouse, a hop-pivot home, a blink */
      const t = p * 2.6;
      hop(o, t, 0.0, 0.22, 0.16); hop(o, t, 0.72, 0.22, 0.16); hop(o, t, 2.0, 0.2, 0.16);
      o('pose', 'ry', (PI / 2) * sst(0.14, 0.3, t) - PI * sst(0.86, 1.02, t) + (PI / 2) * sst(2.14, 2.3, t));
      const a1 = hold(t, 0.14, 0.3, 0.04), a2 = hold(t, 0.86, 1.02, 0.04), a3 = hold(t, 2.14, 2.3, 0.04);
      wings(o, 0.5 * (a1 + a2 + a3), 0.45 * Math.sin(TAU * 12 * t) * (a1 + a2 + a3));
      const g1 = hold(t, 0.36, 0.72, 0.022);
      o('head', 'ry', -1.0 * g1); o('head', 'rz', -0.3 * g1); blink(o, t, 0.36, 0.1);
      flick(o, -1, t, 0.5);
      tail(o, -0.35 * bump(t, 0.52, 0.7)); fan(o, 0.35 * bump(t, 0.52, 0.72));
      const g2 = hold(t, 1.06, 1.32, 0.03);
      o('head', 'ry', 2.1 * g2); o('head', 'rz', 0.6 * g2); o('neck', 'ry', 0.1 * g2); blink(o, t, 1.06, 0.1);
      const wipe = hold(t, 1.32, 1.62, 0.1);
      o('head', 'rx', 1.0 * wipe); o('neck', 'pz', 0.04 * wipe); o('body', 'rx', 0.2 * wipe);
      o('head', 'rz', 0.45 * bump(t, 1.4, 1.5) - 0.45 * bump(t, 1.51, 1.61)); o('head', 'ry', 0.25 * bump(t, 1.4, 1.5) - 0.25 * bump(t, 1.51, 1.61));
      blink(o, t, 1.62, 0.1);
      const rouse = hold(t, 1.66, 2.0, 0.12), shake = osc(t, 1.7, 2.0, 12);
      o('body', 's', 0.1 * rouse); o('head', 's', 0.08 * rouse);
      o('body', 'rz', 0.1 * shake); o('head', 'rz', -0.08 * shake); tail(o, 0, 0.12 * shake);
      wings(o, 0.15 * rouse, 0.15 * shake);
      o('head', 'ry', 0.2 * rouse);
      blink(o, t, 2.36, 0.12);
      o('ctl', 'look', hold(t, 0.0, 2.5, 0.05));
    } },
  };
  return K.finish(R);
}

export default {
  id: 'chickadee',
  name: 'Black-capped chickadee',
  latin: 'Poecile atricapillus',
  rests: 'perch',
  build: (THREE, kit) => buildChickadee(THREE, kit),
  update: (rig, dt, state) => rig.kit.update(rig, dt, state),
  play: (rig, clip, variant) => rig.kit.play(rig, clip, variant),
  rest: (rig) => rig.kit.rest(rig),
};
