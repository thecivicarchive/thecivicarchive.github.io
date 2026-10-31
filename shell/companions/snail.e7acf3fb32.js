/*
  The Civic Archive companion: the garden snail (Cornu aspersum).

  Built on the companions' realism kit (kit.js). The shell is a real one: TinyWorlds' CC0 photogrammetry scan of a
  land-snail shell (models/snail/shell.glb, 444 KB, credited in credits.json), turned into its own frame (coiling axis
  up, the aperture at the front) and stretched 1.175x along its coiling axis to Cornu's proportions; the scan's own
  growth lines ride on its normal map. Its colour is not a texture but Cornu's pattern painted by this module's fragment
  shader from the surface itself (a buff ground streaked along the growth lines, five interrupted chestnut bands at
  fixed latitudes of the whorl, broken by pale flecks, a worn pale apex, a whitish reflected lip), so it stays crisp
  however close the camera comes. It is worn as the living animal wears it: the apex to the snail's right, up and back
  (dextral), the big body whorl over the back, the aperture facing down and forward onto the mantle, the spire's spiral
  toward the reader. Everything soft is sculpted in code as signed distance fields: the long foot with its flat
  sole and pale fringe, the mantle that fills the aperture with a thick collar at the lip and the breathing pore on the
  snail's right, the arched neck and the blunt head, all one skinned surface over the body, tail, neck and head bones.
  The skin is reticulated: polygonal tubercles (a cellular pattern pressed into the field, elongated along the body)
  parted by darker grooves, wet with a clearcoat; two dark lines run back from the eyestalks along the neck, as Cornu's
  do. The two eyestalks are skinned over a base bone and a tip bone, so they shorten by invagination (the tip sinks
  toward the base) and bend only at the base, as the real ones do; the eyes are the kit's wet eyes, lidless, black
  points at the swollen tips. The lower tentacles tap the ground ahead. A snail does not blink: its "blink" is one
  stalk's tip quivering and shortening a little, never both at once. A faint glistening trail lies behind the tail.

  export default { id, name, latin, rests, build(THREE, kit) -> Promise<rig>, update(rig, dt, state), play(rig, clip) -> seconds, rest(rig) }
    rig.root   1 unit = the height to the top of the shell (about 33 mm), facing +z toward the viewer, the sole at y = 0
    rig.frame  the box, in root units, a camera should keep in view
    clips      arrive, idleA, idleB (two versions), notice, react, talk, lookLeft, lookRight, rest, dance (two versions);
               every clip ends exactly on the rest pose
  Motion notes (research/snail.md): the glide is a smooth translation, since the pedal waves run on the sole and never
  show from the side; tentacles extend hydraulically, bend about their base with a straight stem, scan continuously each
  on its own rhythm, and pull in fast on a touch (0.3 s), hold, and come back out slowly, less each time (habituation);
  nothing about a snail is quick except that pull-in; every turn starts late and settles with weight; the breathing
  pore opens and closes only a few times a minute; the shell rides on its columellar muscle and rocks a little after
  each move. The hover dance is "the semaphore" (research/snail.md, section 3), made only of movements the animal makes.
*/

async function buildSnail(THREE, K) {
  if (!K || !K.rig) throw new Error('the snail needs the companions kit: build(THREE, kit)');
  const { sd, surf, prim, rgb, mixc, fbm, noise, sst, lerp, clamp, unit, cross, dot } = K;
  const PI = Math.PI, TAU = 2 * PI;
  const YAW = 1.42;                 /* it crawls toward the viewer's right, a little toward them, so its right flank shows and the spire's spiral faces the reader (dextral: the spire is on the snail's right) */
  const FACE = -YAW;                /* how far the head turns to look straight at the person */
  const R = K.rig({
    id: 'snail', yaw: YAW, frame: { x: [-0.62, 0.62], y: [-0.03, 0.96] }, fov: 36,
    breath: 0.14, look: { yaw: 0.55, pitch: 0.3, speed: 2.6 },
    idles: ['idleA', 'idleB', 'idleB', 'lookLeft', 'lookRight', 'notice'],
  });
  const SNL = { lastReact: -99, side: 1, prevBlink: -1 };      /* the module's own small memory: habituation, which stalk blinks */
  const V3 = (a) => new THREE.Vector3(a[0], a[1], a[2]);
  const arr = (v) => [v.x, v.y, v.z];
  /* an Euler whose rotation carries the axes onto the given right-handed basis (the kit's sd.* take Eulers) */
  const basisEuler = (xv, yv, zv) => { const e = new THREE.Euler().setFromRotationMatrix(new THREE.Matrix4().makeBasis(V3(xv), V3(yv), V3(zv))); return [e.x, e.y, e.z]; };

  /* ---------- the shell: loaded first, so the body can be sculpted to its aperture ---------- */
  const model = await K.loadModel('models/snail/shell.glb');
  const extras = (model.gltf && (model.gltf.userData || (model.gltf.parser && model.gltf.parser.json && model.gltf.parser.json.extras))) || {};
  /* the file's own frame (its extras say the same): coiling axis +Y with the apex up, the aperture on the +X side facing +Z and down */
  const apert = (extras.aperture && extras.aperture.centre) ? extras.aperture : { centre: [0.139, -0.143, 0.211], outwardNormal: [0, -0.576, 0.817], reach: 0.471 };
  /* the aperture's rim, measured on the mesh: an oval, 0.89 by 0.62 across, its long axis 52 degrees from the coiling
     axis in the aperture's plane, its centre a little off the rim's mean point */
  const RIM = { a: 0.447, b: 0.31, angle: 0.907, da: -0.022, db: -0.028 };
  /* wearing it: the apex to the snail's right (-x), up and back; the aperture facing down and forward, its centre low
     over the rear half of the foot. The roll about the apex is chosen so the aperture faces as near `face` as the shell
     allows (the angle between the apex and the aperture's normal is the shell's own, 125 degrees) */
  const SHELL = { k: 0.95, apex: unit([-0.84, 0.36, -0.36]), face: unit([0.1, -0.74, 0.66]), at: [0.01, 0.37, 0.1] };
  const Yw = V3(SHELL.apex), Nd = V3(SHELL.face);
  const Zw = Nd.clone().addScaledVector(Yw, -Nd.dot(Yw)).normalize(), Xw = new THREE.Vector3().crossVectors(Yw, Zw);
  const shellM = new THREE.Matrix4().makeBasis(Xw, Yw, Zw);
  const shellE = new THREE.Euler().setFromRotationMatrix(shellM);
  const rotS = (d) => arr(V3(d).applyMatrix4(shellM));
  const capRot = rotS(apert.centre);
  SHELL.pos = [SHELL.at[0] - SHELL.k * capRot[0], SHELL.at[1] - SHELL.k * capRot[1], SHELL.at[2] - SHELL.k * capRot[2]];
  const toSculpt = (p) => { const v = rotS(p); return [v[0] * SHELL.k + SHELL.pos[0], v[1] * SHELL.k + SHELL.pos[1], v[2] * SHELL.k + SHELL.pos[2]]; };
  const dirSculpt = (d) => unit(rotS(d));
  const apC = toSculpt(apert.centre), apN = dirSculpt(apert.outwardNormal);
  /* the aperture's oval in sculpting space: axes along and across the opening, and the plane's normal */
  const uC = (() => { const n = V3(apert.outwardNormal).normalize(), u = new THREE.Vector3(0, 1, 0); u.addScaledVector(n, -u.dot(n)).normalize(); return { u: arr(u), v: arr(new THREE.Vector3().crossVectors(n, u)) }; })();
  const ca = Math.cos(RIM.angle), sa = Math.sin(RIM.angle);
  const aDir = dirSculpt([uC.u[0] * ca + uC.v[0] * sa, uC.u[1] * ca + uC.v[1] * sa, uC.u[2] * ca + uC.v[2] * sa]);
  const bDir = dirSculpt([-uC.u[0] * sa + uC.v[0] * ca, -uC.u[1] * sa + uC.v[1] * ca, -uC.u[2] * sa + uC.v[2] * ca]);
  const apA = RIM.a * SHELL.k, apB = RIM.b * SHELL.k;
  const apO = [apC[0] + aDir[0] * RIM.da * SHELL.k + bDir[0] * RIM.db * SHELL.k, apC[1] + aDir[1] * RIM.da * SHELL.k + bDir[1] * RIM.db * SHELL.k, apC[2] + aDir[2] * RIM.da * SHELL.k + bDir[2] * RIM.db * SHELL.k];
  const apEuler = basisEuler(aDir, bDir, apN);
  /* a point on the rim's oval in the direction d (any vector; its part in the plane is used), pushed out by `out` */
  const rimPoint = (d, out = 0) => {
    const pa = dot(d, aDir), pb = dot(d, bDir), th = Math.atan2(pb / apB, pa / apA), qa = apA * Math.cos(th), qb = apB * Math.sin(th);
    return [apO[0] + aDir[0] * qa + bDir[0] * qb + apN[0] * out, apO[1] + aDir[1] * qa + bDir[1] * qb + apN[1] * out, apO[2] + aDir[2] * qa + bDir[2] * qb + apN[2] * out];
  };
  const eRight = unit(cross(apN, [0, 1, 0]));      /* the snail's right along the collar (the pore side) */

  /* ---------- colours: grey-brown skin, a paler fringe and collar, dark grooves and eyes ---------- */
  const SKIN = rgb(0x6f6253), SKIN2 = rgb(0x4a3f35), SKIN3 = rgb(0x8e8271), RIMC = rgb(0xa89d8b), COLLAR = rgb(0x8f8272), LINE = rgb(0x3a3028);
  const PORE = rgb(0x1f1a16);

  /* ---------- the skin's reticulation: a cellular pattern, each cell a tubercle, the seams between them grooves ---------- */
  const hsh = (i, j, k, s) => {
    let h = Math.imul(i, 0x8da6b343) ^ Math.imul(j, 0xd8163841) ^ Math.imul(k, 0xcb1ab31f) ^ Math.imul(s, 0x165667b1);
    h = Math.imul(h ^ (h >>> 13), 0x5bd1e995); h ^= h >>> 15;
    return (h >>> 0) / 4294967296;
  };
  /* the gap between the nearest two tubercle centres (0 on a seam) for a point, in cells elongated along the body and
     laid in slanting rows; about a millimetre each on the living animal */
  const seam = (x, y, z) => {
    const X = x * 50 + 0.3 * z, Y = y * 44 + 0.25 * z, Z = z * 28 + 0.3 * Math.sin(x * 9);
    const i = Math.floor(X), j = Math.floor(Y), k = Math.floor(Z);
    let f1 = 9, f2 = 9;
    for (let a = -1; a <= 1; a++) for (let b = -1; b <= 1; b++) for (let c = -1; c <= 1; c++) {
      const ci = i + a, cj = j + b, ck = k + c;
      const dx = ci + 0.15 + 0.7 * hsh(ci, cj, ck, 1) - X, dy = cj + 0.15 + 0.7 * hsh(ci, cj, ck, 2) - Y, dz = ck + 0.15 + 0.7 * hsh(ci, cj, ck, 3) - Z;
      const d = dx * dx + dy * dy + dz * dz;
      if (d < f1) { f2 = f1; f1 = d; } else if (d < f2) f2 = d;
    }
    return Math.sqrt(f2) - Math.sqrt(f1);
  };
  /* the paint and the material ask about the same vertex in turn: the last answer is kept */
  let mX = NaN, mY = NaN, mZ = NaN, mG = 0;
  const seamAt = (x, y, z) => { if (x === mX && y === mY && z === mZ) return mG; mX = x; mY = y; mZ = z; return (mG = seam(x, y, z)); };

  /* ---------- the body as one field: foot, mantle, collar, neck, head ---------- */
  /* the foot: long and low, wider than tall, with a flat sole; its spine runs the whole length and it narrows to the tail */
  const sole = sd.xf(sd.chain(
    [[0, 0.015, -0.8], [0, 0.04, -0.67], [0, 0.065, -0.52], [0, 0.082, -0.33], [0, 0.09, -0.08], [0, 0.09, 0.18], [0, 0.086, 0.38], [0, 0.08, 0.53], [0, 0.072, 0.63]],
    [0.018, 0.045, 0.078, 0.095, 0.1, 0.1, 0.096, 0.088, 0.072], 0.03), [0, 0, 0], null, [1.5, 1, 1]);
  /* the mantle: a dome that fills the aperture's oval (the shell's lip rests on it), and the thick rolled collar at the lip */
  const mantle = sd.egg([apO[0] - apN[0] * 0.03, apO[1] - apN[1] * 0.03, apO[2] - apN[2] * 0.03], [apA * 1.06, apB * 1.06, 0.15 * SHELL.k], apEuler);
  const collar = (() => {
    const c = [apO[0] + apN[0] * 0.02, apO[1] + apN[1] * 0.02, apO[2] + apN[2] * 0.02], rm = 0.04 * SHELL.k;
    const f = (x, y, z) => {
      const px = x - c[0], py = y - c[1], pz = z - c[2];
      const pa = px * aDir[0] + py * aDir[1] + pz * aDir[2], pb = px * bDir[0] + py * bDir[1] + pz * bDir[2], pn = px * apN[0] + py * apN[1] + pz * apN[2];
      const th = Math.atan2(pb / apB, pa / apA), qa = apA * Math.cos(th) - pa, qb = apB * Math.sin(th) - pb;
      return Math.sqrt(qa * qa + qb * qb + pn * pn) - rm;
    };
    f.b = [c[0], c[1], c[2], apA + rm]; return f;
  })();
  /* the neck comes out of the lower front of the aperture, rises a little and arches forward and down to the head,
     tapering over its front third to the blunt head */
  const neck = sd.xf(sd.chain(
    [[0, 0.3, apC[2] - 0.08], [0, 0.31, apC[2] + 0.1], [0, 0.27, 0.34], [0, 0.205, 0.45], [0, 0.15, 0.54], [0, 0.115, 0.61], [0, 0.095, 0.66]],
    [0.165, 0.152, 0.126, 0.104, 0.088, 0.076, 0.064], 0.03), [0, 0, 0], null, [1.22, 1, 1]);
  const smooth = sd.add(0.07, sd.add(0.08, sole, mantle), sd.add(0.045, neck, collar));
  /* the skin's grain: tubercles parted by grooves everywhere but the sole and its fringe, pressed into the field near
     its surface only (the pattern is dear to compute) */
  const bodyF = (x, y, z) => {
    const d = smooth(x, y, z);
    if (Math.abs(d) > 0.012) return d;
    const m = sst(0.045, 0.1, y) * (1 - 0.7 * sst(0.01, -0.02, collar(x, y, z)));      /* the collar is smoother */
    const g = seam(x, y, z);
    return d + m * 0.0021 * (sst(0.26, 0.0, g) - 0.4);
  };
  bodyF.b = smooth.b;
  const bodyS = sd.cut(bodyF, [0, 0, 0], [0, -1, 0], 0.014);      /* the sole, flat on the ground, with a rounded edge */

  /* painting the skin: darker in the grooves between tubercles, lighter on their tops; two dark lines run back from
     the eyestalks along the neck, as Cornu's do; the foot's fringe is pale with fine vertical creases; the collar paler */
  const skinAt = (x, y, z, nx, ny) => {
    const g = seamAt(x, y, z), top = sst(0.06, 0.3, g), h = noise(x * 150, y * 150, z * 150);
    let c = mixc(SKIN2, SKIN, 0.78 + 0.22 * top);
    c = mixc(c, SKIN3, 0.4 * top * sst(0.4, 0.8, h));
    c = mixc(c, SKIN2, 0.3 * sst(0.3, -0.2, ny));                                       /* the underside of the body is darker */
    c = mixc(c, SKIN2, 0.22 * sst(0.45, 0.85, ny) * sst(0.1, 0.2, y) * sst(0.5, 0.0, Math.abs(x) - 0.08));      /* and so is the back of the neck, as Cornu's dorsum is */
    const line = sst(0.024, 0.009, Math.abs(Math.abs(x) - 0.055 - 0.012 * (z - 0.3))) * sst(0.1, 0.24, z) * sst(0.6, 0.5, z) * sst(0.05, 0.25, ny);
    c = mixc(c, LINE, 0.6 * line);
    const fringe = sst(0.05, 0.016, y);
    c = mixc(c, RIMC, 0.8 * fringe * (0.8 + 0.2 * Math.sin(z * 140 + 2 * noise(z * 30, 1, 1))));      /* the pale fringe of the foot */
    const col = collar(x, y, z);
    c = mixc(c, COLLAR, 0.65 * sst(0.02, -0.01, col));
    return c;
  };
  /* per vertex: rougher in the grooves, glossier on the tubercle tops and the collar */
  const skinMat = (x, y, z) => {
    const top = sst(0.06, 0.3, seamAt(x, y, z)), col = sst(0.02, -0.01, collar(x, y, z));
    return [lerp(1.15, 0.75, Math.max(top, col)), lerp(0.7, 1.3, Math.max(top, col)), 1];
  };

  /* materials */
  const skin = K.physical({ rough: 0.5, clearcoat: 0.5, ccRough: 0.26, sheen: 0.12, sheenRough: 0.6, spec: 0.5, name: 'snail-skin' });
  const stalkM = K.physical({ rough: 0.46, clearcoat: 0.5, ccRough: 0.26, sheen: 0.1, spec: 0.5, name: 'snail-stalk' });
  const tentM = K.physical({ rough: 0.46, clearcoat: 0.5, ccRough: 0.26, sheen: 0.1, spec: 0.5, name: 'snail-tentacle' });
  const poreM = K.physical({ rough: 0.35, clearcoat: 0.6, ccRough: 0.2, spec: 0.5, name: 'snail-pore' });

  /* ---------- joints (bones) ---------- */
  K.joint(R, 'body', 'pose', [0, 0.1, -0.1]);
  K.joint(R, 'tail', 'body', [0, 0.05, -0.4]);
  K.joint(R, 'shell', 'body', [apC[0] - apN[0] * 0.12, apC[1] - apN[1] * 0.12, apC[2] - apN[2] * 0.12]);      /* the columellar muscle: it rocks about its attachment */
  K.joint(R, 'neck', 'body', [0, 0.28, 0.22]);
  K.joint(R, 'head', 'neck', [0, 0.18, 0.46]);
  K.limit(R, 'head', { ry: [-1.3, 1.3], rx: [-0.8, 0.7], rz: [-0.5, 0.5] });
  K.limit(R, 'neck', { ry: [-0.8, 0.8], rx: [-0.6, 0.5] });

  /* the skinned body */
  const bodyGeo = surf(bodyS, [-0.44, -0.02, -0.84, 0.44, 0.66, 0.72], 0.0085, skinAt, { ao: bodyS, matAt: skinMat, aoStep: 0.02 });
  K.skin(R, bodyGeo, [
    { j: 'body', a: [0, 0.12, -0.4], b: [0, 0.22, 0.12], r: 0.3, only: (x, y, z) => sst(0.36, 0.16, z) },
    { j: 'tail', a: [0, 0.05, -0.42], b: [0, 0.02, -0.8], r: 0.1, only: (x, y, z) => sst(-0.26, -0.44, z) },
    { j: 'neck', a: [0, 0.29, 0.18], b: [0, 0.22, 0.4], r: 0.16, only: (x, y, z) => sst(0.02, 0.16, z) },
    { j: 'head', a: [0, 0.17, 0.44], b: [0, 0.12, 0.68], r: 0.13, only: (x, y, z) => sst(0.32, 0.44, z) },
  ], skin, { smooth: 3, name: 'snail-body' });

  /* the shell on its joint, as the kit's physical material: a clearcoat over the scan's normal and roughness maps, both
     sides drawn. Its colour is not a texture (the scan's one UV island is stretched twenty-fold on the far side, which
     smears any map) but Cornu's pattern painted in the fragment shader from the surface itself: the bands of a helicid
     shell lie at fixed latitudes of the whorl's tube, and on a tube the latitude is the angle of the surface normal in the
     plane through the coiling axis, so five interrupted chestnut bands sit at five such angles, broken by pale flecks,
     over a buff ground streaked along the growth lines (constant angle about the axis); the lip near the aperture's
     plane is whitish and the apex worn pale */
  const SHELL_FRAG = `
varying vec3 vSnP; varying vec3 vSnN;
uniform vec3 uApC; uniform vec3 uApN;
float snHash(vec2 p){ vec3 q = fract(vec3(p.xyx) * vec3(0.1031, 0.1030, 0.0973)); q += dot(q, q.yzx + 33.33); return fract((q.x + q.y) * q.z); }
float snNoise(vec2 p){ vec2 i = floor(p), f = fract(p); f = f * f * (3.0 - 2.0 * f); return mix(mix(snHash(i), snHash(i + vec2(1.0, 0.0)), f.x), mix(snHash(i + vec2(0.0, 1.0)), snHash(i + vec2(1.0, 1.0)), f.x), f.y); }
vec3 tcaShell(vec3 p, vec3 n) {
  float rho = length(p.xz);
  vec2 radial = rho > 1e-4 ? p.xz / rho : vec2(1.0, 0.0);
  float lat = atan(n.y, dot(n.xz, radial));
  float th = atan(p.z, p.x);
  float turn = th * 1.4324 + p.y * 2.5;
  float streak = 0.6 * snNoise(vec2(turn * 5.0, lat * 1.2)) + 0.4 * snNoise(vec2(turn * 23.0, lat * 2.0));
  float fleck = 0.7 * snNoise(vec2(turn * 8.0, lat * 3.2 + 7.0)) + 0.3 * snNoise(vec2(turn * 21.0 + 3.0, lat * 6.0));
  float lines = snNoise(vec2(turn * 64.0, lat * 2.0 + 3.0));
  vec3 buff = vec3(0.52, 0.38, 0.22), pale = vec3(0.74, 0.62, 0.43), chestnut = vec3(0.27, 0.15, 0.08), dark = vec3(0.15, 0.08, 0.045);
  vec3 c = mix(buff, pale, 0.15 + 0.45 * streak);
  c = mix(c, chestnut, 0.2 * smoothstep(0.55, 0.85, lines) + 0.14 * smoothstep(0.6, 0.85, streak) * smoothstep(0.3, 0.7, lines));
  float wob = 0.12 * (streak - 0.5) + 0.06 * (fleck - 0.5);
  float band = 0.0;
  band = max(band, smoothstep(0.17, 0.09, abs(lat - 1.02 - wob)));
  band = max(band, smoothstep(0.13, 0.06, abs(lat - 0.62 - wob)));
  band = max(band, smoothstep(0.21, 0.11, abs(lat - 0.12 - wob)));
  band = max(band, smoothstep(0.15, 0.07, abs(lat + 0.40 - wob)));
  band = max(band, smoothstep(0.13, 0.06, abs(lat + 0.86 - wob)));
  float broken = smoothstep(0.52, 0.7, fleck);
  c = mix(c, mix(chestnut, dark, 0.5 * fleck), band * (1.0 - 0.82 * broken));
  float lip = smoothstep(-0.075, -0.012, dot(p - uApC, uApN));
  c = mix(c, vec3(0.86, 0.82, 0.74), lip);
  float apex = smoothstep(0.26, 0.04, rho) * smoothstep(0.08, 0.4, p.y);
  c = mix(c, pale, 0.7 * apex);
  c = mix(c, pale, 0.3 * smoothstep(-0.9, -1.45, lat));
  if (!gl_FrontFacing) c *= 0.45;
  return pow(c, vec3(2.2));
}
`;
  const shellMeshes = K.dress(model.scene, { mat: { clearcoat: 0.34, ccRough: 0.28, rough: 0.55, spec: 0.5, env: 0.9, side: THREE.DoubleSide, normalScale: 0.9 } });
  for (const x of shellMeshes) {
    const m = x.material, prev = m.onBeforeCompile;
    m.onBeforeCompile = (sh) => {
      if (prev) prev(sh);
      sh.uniforms.uApC = { value: new THREE.Vector3(apert.centre[0], apert.centre[1], apert.centre[2]) };
      sh.uniforms.uApN = { value: new THREE.Vector3(apert.outwardNormal[0], apert.outwardNormal[1], apert.outwardNormal[2]).normalize() };
      sh.vertexShader = sh.vertexShader
        .replace('#include <common>', '#include <common>\nvarying vec3 vSnP; varying vec3 vSnN;')
        .replace('#include <project_vertex>', 'vSnP = position; vSnN = normal;\n#include <project_vertex>');
      sh.fragmentShader = sh.fragmentShader
        .replace('#include <common>', '#include <common>\n' + SHELL_FRAG)
        .replace('#include <map_fragment>', '#include <map_fragment>\ndiffuseColor.rgb *= tcaShell(vSnP, normalize(vSnN));');
    };
    m.customProgramCacheKey = () => 'tca-phys-2-snail-shell';
    m.needsUpdate = true;
  }
  {
    const holder = new THREE.Group(); holder.name = 'shell-holder';
    const pv = R.piv.shell;
    holder.position.set(SHELL.pos[0] - pv[0], SHELL.pos[1] - pv[1], SHELL.pos[2] - pv[2]);
    holder.rotation.copy(shellE); holder.scale.setScalar(SHELL.k);
    holder.add(model.scene); R.j.shell.add(holder);
    for (const x of model.meshes) { R.geos.push(x.geometry); R.mats.add(x.material); }
  }

  /* ---------- the eyestalks: a base bone and a tip bone, the eye at the tip ---------- */
  const STALK = { L: 0.38, r0: 0.024, r1: 0.0125, bulb: 0.0235 };
  const HALF = STALK.L / 2;
  const stalkPaint = (x, y, z) => {
    const g = fbm(x * 110, y * 110, z * 110, 2);
    let c = mixc(SKIN, SKIN2, 0.15 + 0.35 * sst(0.6, 0.3, g));
    c = mixc(c, SKIN3, 0.5 * sst(0.5, 0.85, g));
    return c;
  };
  const stalkMat = (x, y, z) => { const g = fbm(x * 110, y * 110, z * 110, 2), top = sst(0.5, 0.75, g); return [lerp(1.1, 0.75, top), lerp(0.8, 1.2, top), 1]; };
  for (const s of [1, -1]) {
    const side = s > 0 ? 'L' : 'R';
    const base = [s * 0.048, 0.245, 0.515], d = unit([s * 0.3, 0.9, 0.34]);
    const tip = [base[0] + d[0] * STALK.L, base[1] + d[1] * STALK.L, base[2] + d[2] * STALK.L];
    const mid = [base[0] + d[0] * HALF, base[1] + d[1] * HALF, base[2] + d[2] * HALF];
    const q = new THREE.Quaternion().setFromUnitVectors(new THREE.Vector3(0, 1, 0), new THREE.Vector3(d[0], d[1], d[2]));
    const e = new THREE.Euler().setFromQuaternion(q);
    K.joint(R, 'stalk' + side, 'head', base, [e.x, e.y, e.z]);
    K.local(R, 'tip' + side, 'stalk' + side, [0, HALF, 0]);
    K.limit(R, 'tip' + side, { py: [-HALF * 0.92, HALF * 0.14] });
    K.limit(R, 'stalk' + side, { rz: [-1.0, 1.0], rx: [-0.45, 1.6] });
    /* the stalk in the sculpting space: a tapered stem, a swollen tip, a flare that sinks into the head */
    const root = [base[0] - d[0] * 0.035, base[1] - d[1] * 0.035, base[2] - d[2] * 0.035];
    const stem = sd.add(0.014, sd.limb(root, tip, STALK.r0 * 1.2, STALK.r1), sd.ball(tip, STALK.bulb), sd.ball([base[0] - d[0] * 0.014, base[1] - d[1] * 0.014, base[2] - d[2] * 0.014], 0.04));
    const grainy = (x, y, z) => stem(x, y, z) + 0.0014 * (fbm(x * 110, y * 110, z * 110, 2) - 0.5);
    grainy.b = stem.b;
    const lo = [Math.min(root[0], tip[0]) - 0.05, Math.min(root[1], tip[1]) - 0.05, Math.min(root[2], tip[2]) - 0.05];
    const hi = [Math.max(root[0], tip[0]) + 0.05, Math.max(root[1], tip[1]) + 0.05, Math.max(root[2], tip[2]) + 0.05];
    const geo = surf(grainy, [lo[0], lo[1], lo[2], hi[0], hi[1], hi[2]], 0.0042, stalkPaint, { ao: sd.min(grainy, bodyS), matAt: stalkMat, aoStep: 0.012 });
    K.skin(R, geo, [
      { j: 'stalk' + side, a: root, b: mid, r: 0.05 },
      { j: 'tip' + side, a: mid, b: tip, r: 0.05 },
    ], s > 0 ? stalkM : K.physical({ rough: 0.46, clearcoat: 0.5, ccRough: 0.26, sheen: 0.1, spec: 0.5, name: 'snail-stalk-r' }), { smooth: 4, name: 'snail-stalk' + side });
    /* the eye: a black point on the front of the bulb, wet, with a glint; a snail has no lids, so the kit's are hidden */
    const ed = unit([s * 0.3, 0.3, 0.9]), er = 0.0095, bc = STALK.bulb - er * 0.45;
    K.eye(R, 'eye' + side, 'tip' + side, [ed[0] * bc, HALF + ed[1] * bc, ed[2] * bc], ed, er, {
      isLocal: true, iris: 0x1a120c, iris2: 0x2a1c12, pupil: 0.55, irisAngle: 1.25, sclera: 0x4a4038, limbal: 0x0c0806, gloss: 0.85, wet: 0.5, glint: 0.32, glintA: 0.8, lower: false, lid: SKIN, lidMat: { rough: 0.5, name: 'snail-eyelid' + side },
    });
    R.j['eye' + side + 'Lid'].visible = false;
  }
  R.lids = R.lids.filter((l) => !/^eye/.test(l.n));
  /* the snail's blink: one stalk's tip quivers and sinks a fifth of the way, chosen anew each time (see life) */
  R.lids.push({ n: 'tipL', ch: 'py', get shut() { return SNL.side > 0 ? -HALF * 0.22 : 0; } });
  R.lids.push({ n: 'tipR', ch: 'py', get shut() { return SNL.side < 0 ? -HALF * 0.22 : 0; } });
  R.lids.push({ n: 'stalkL', ch: 'rz', get shut() { return SNL.side > 0 ? 0.07 * Math.sin(R.t * 57) : 0; } });
  R.lids.push({ n: 'stalkR', ch: 'rz', get shut() { return SNL.side < 0 ? 0.07 * Math.sin(R.t * 57) : 0; } });

  /* ---------- the lower tentacles: short, tactile, tapping the ground ahead ---------- */
  for (const s of [1, -1]) {
    const side = s > 0 ? 'L' : 'R';
    const base = [s * 0.046, 0.075, 0.625], d = unit([s * 0.42, -0.4, 0.82]);
    const q = new THREE.Quaternion().setFromUnitVectors(new THREE.Vector3(0, 1, 0), new THREE.Vector3(d[0], d[1], d[2]));
    const e = new THREE.Euler().setFromQuaternion(q);
    K.joint(R, 'tent' + side, 'head', base, [e.x, e.y, e.z]);
    K.limit(R, 'tent' + side, { rx: [-0.9, 0.9], rz: [-0.8, 0.8], sy: [-0.75, 0.3] });
    const Lt = 0.13;
    const f = sd.add(0.008, sd.limb([0, -0.03, 0], [0, Lt, 0], 0.017, 0.0085), sd.ball([0, Lt, 0], 0.012), sd.ball([0, -0.015, 0], 0.026));
    const g = (x, y, z) => f(x, y, z) + 0.0009 * (fbm(x * 130, y * 130, z * 130, 2) - 0.5);
    g.b = f.b;
    const geo = surf(g, [-0.032, -0.046, -0.032, 0.032, Lt + 0.02, 0.032], 0.0032, (x, y, z) => mixc(stalkPaint(x, y, z), SKIN2, 0.25 * sst(Lt - 0.02, Lt, y)), { matAt: stalkMat, aoStep: 0.01 });
    K.put(R, 'tent' + side, geo, s > 0 ? tentM : K.physical({ rough: 0.46, clearcoat: 0.5, ccRough: 0.26, sheen: 0.1, spec: 0.5, name: 'snail-tentacle-r' }), true);
  }

  /* ---------- the breathing pore, on the snail's right under the shell's lip; it opens and closes slowly ---------- */
  {
    const c = rimPoint([eRight[0] + 0.0, eRight[1] + 0.35, eRight[2]], 0.064 * SHELL.k);      /* on the collar's outer face (its centreline is 0.02 out, its radius 0.04), a little above the middle of the right side */
    const n = unit([eRight[0] * 0.7 + apN[0] * 0.6, eRight[1] * 0.7 + apN[1] * 0.6 + 0.1, eRight[2] * 0.7 + apN[2] * 0.6]);
    const q = new THREE.Quaternion().setFromUnitVectors(new THREE.Vector3(0, 0, 1), new THREE.Vector3(n[0], n[1], n[2]));
    const e = new THREE.Euler().setFromQuaternion(q);
    const pv = R.piv.body;
    K.local(R, 'pore', 'body', [c[0] - pv[0], c[1] - pv[1], c[2] - pv[2]], [e.x, e.y, e.z]);
    const g = new THREE.SphereGeometry(0.03, 16, 10); g.scale(1, 0.7, 0.3);
    K.put(R, 'pore', prim(g, (x, y, z) => mixc(PORE, SKIN2, 0.5 * sst(0.012, 0.028, Math.hypot(x, y))), 0.8), poreM, true);
    K.limit(R, 'pore', { sx: [-0.92, 0.3], sy: [-0.92, 0.3], sz: [-0.92, 0.3] });
  }

  /* ---------- the trail: a faint glistening band on the page behind the tail ---------- */
  {
    const g = new THREE.PlaneGeometry(0.2, 0.85, 2, 16); g.rotateX(-PI / 2);
    const P = g.attributes.position, n = P.count, col = new Float32Array(n * 4);
    for (let i = 0; i < n; i++) {
      const u = (P.getX(i) / 0.2) * 2, v = (-P.getZ(i) + 0.425) / 0.85;      /* v: 0 at the tail end, 1 far behind */
      const a = 0.7 * (1 - sst(0.2, 1, v)) * sst(1.0, 0.55, Math.abs(u)) * (0.75 + 0.25 * noise(u * 3, v * 14, 1));
      col[4 * i] = 0.84; col[4 * i + 1] = 0.83; col[4 * i + 2] = 0.8; col[4 * i + 3] = a;
    }
    g.setAttribute('color', new THREE.BufferAttribute(col, 4));
    const m = K.physical({ rough: 0.08, clearcoat: 1, ccRough: 0.04, spec: 1, env: 1.8, transparent: true, depthWrite: false, name: 'snail-trail' });
    const trail = new THREE.Mesh(g, m); trail.name = 'snail-trail'; trail.renderOrder = -1; trail.castShadow = false; trail.receiveShadow = false; trail.frustumCulled = false;
    trail.rotation.y = YAW;
    trail.position.set(-Math.sin(YAW) * 1.15, 0.0025, -Math.cos(YAW) * 1.15);
    R.root.add(trail); R.geos.push(g); R.mats.add(m);
  }

  /* ---------- secondary motion: the shell settles on its muscle; the stalks and the tail follow through ---------- */
  K.spring(R, 'shell', { ch: 'rx', k: 60, c: 7.5, gain: 0.05, dir: [0, 1, 0], lim: [-0.14, 0.14] });
  K.spring(R, 'shell', { ch: 'rz', k: 60, c: 7.5, gain: 0.035, dir: [0, 1, 0], lim: [-0.1, 0.1] });
  K.spring(R, 'stalkL', { ch: 'rz', k: 150, c: 11, gain: 0.02, dir: [0, 1, 0], lim: [-0.3, 0.3] });
  K.spring(R, 'stalkR', { ch: 'rz', k: 150, c: 11, gain: 0.02, dir: [0, 1, 0], lim: [-0.3, 0.3] });
  K.spring(R, 'tail', { ch: 'ry', k: 70, c: 8, gain: 0.03, dir: [0, 0, -1], lim: [-0.25, 0.25] });

  /* ---------- breathing, attention, the continuous scanning of the stalks, the pore's slow cycle ---------- */
  const shorten = (o, side, k) => o(side > 0 ? 'tipL' : 'tipR', 'py', -HALF * k);
  const bendOut = (o, side, v) => o(side > 0 ? 'stalkL' : 'stalkR', 'rz', -side * v);      /* positive v bends a stalk away from the midline */
  const lower = (o, side, v) => o(side > 0 ? 'stalkL' : 'stalkR', 'rx', v);                /* positive v lowers a stalk forward toward horizontal */
  R.spec.life = (o, L) => {
    o('body', 'sx', 0.012 * L.b); o('body', 'sy', 0.01 * L.b);                       /* the mantle collar and the body swell with the slow breath */
    o('neck', 'ry', 0.4 * L.yaw); o('head', 'ry', 0.6 * L.yaw); o('head', 'rx', 0.5 * L.pitch);
    o('stalkL', 'rz', -0.5 * L.yaw); o('stalkR', 'rz', -0.5 * L.yaw);                  /* both stalks lean toward what the head looks at */
    lower(o, 1, 0.45 * L.pitch); lower(o, -1, 0.45 * L.pitch);
    if (L.still) return;
    const t = L.t;
    /* scanning: slow lateral sweeps, each stalk on its own rhythm, a little out of phase; the tips drift in length */
    bendOut(o, 1, 0.2 * Math.sin(t * 0.95 + 0.4) + 0.06 * Math.sin(t * 2.3)); bendOut(o, -1, 0.2 * Math.sin(t * 0.8 + 2.4) + 0.06 * Math.sin(t * 1.9 + 1));
    lower(o, 1, 0.07 * Math.sin(t * 0.6 + 1.1)); lower(o, -1, 0.07 * Math.sin(t * 0.52 + 3.0));
    shorten(o, 1, 0.05 + 0.05 * Math.sin(t * 0.37)); shorten(o, -1, 0.05 + 0.05 * Math.sin(t * 0.43 + 2));
    /* the lower tentacles tap the ground ahead, alternately */
    o('tentL', 'rx', 0.28 * Math.max(0, Math.sin(t * 3.1)) ** 2); o('tentR', 'rx', 0.28 * Math.max(0, Math.sin(t * 3.1 + PI)) ** 2);
    /* the breathing pore: open most of the time, it closes for a couple of seconds a few times a minute */
    const cyc = (t % 47) / 47;
    o('pore', 's', -0.85 * K.HELP.bump(cyc, 0.3, 0.36));
    /* which stalk blinks: chosen when a blink begins */
    if (R.blinkT >= 0 && SNL.prevBlink < 0) SNL.side = R.rnd() < 0.5 ? 1 : -1;
    SNL.prevBlink = R.blinkT;
  };
  /* ducking aside while the person scrolls: the stalks half in, the head down, a shuffle toward the edge */
  R.spec.duck = (o, d) => { shorten(o, 1, 0.5 * d); shorten(o, -1, 0.5 * d); o('head', 'rx', 0.3 * d); o('head', 'pz', -0.05 * d); o('tentL', 'sy', -0.4 * d); o('tentR', 'sy', -0.4 * d); o('mover', 'px', 0.2 * d); };

  /* ---------- clips ---------- */
  const faceTo = (o, e) => { o('neck', 'ry', 0.4 * FACE * e); o('head', 'ry', 0.6 * FACE * e); };
  const converge = (o, e) => { lower(o, 1, 0.95 * e); lower(o, -1, 0.95 * e); bendOut(o, 1, -0.22 * e); bendOut(o, -1, -0.22 * e); };      /* posture iv: both stalks forward, horizontal, at what it approaches */
  const taps = (o, p, n, amp) => { o('tentL', 'rx', amp * Math.max(0, Math.sin(TAU * n * p)) ** 2); o('tentR', 'rx', amp * Math.max(0, Math.sin(TAU * n * p + PI)) ** 2); };
  const quiver = (o, side, p, a, b, hz, dur) => { const w = K.HELP.bump(p, a, b); if (w > 0) bendOut(o, side, 0.07 * Math.sin(TAU * hz * dur * p) * w); };
  const fwd = [Math.sin(YAW), Math.cos(YAW)];
  R.clips = {
    arrive: { dur: 1.8, fadeOut: 1.6, fn(p, o, c) { /* a plain glide in along its own line, from behind and to the left, at a stated time-lapse pace; the stalks come out as it comes */
      const u = c.ramp(p, 0, 0.92), back = 0.5 * (1 - u);
      o('mover', 'px', -fwd[0] * back); o('mover', 'pz', -fwd[1] * back);
      const drawn = 0.5 * (1 - c.ramp(p, 0.25, 0.95));
      shorten(o, 1, drawn); shorten(o, -1, drawn * 0.9);
      taps(o, p, 1.8, 0.3 * (1 - c.ramp(p, 0.8, 1)));
      o('head', 'rx', -0.08 * c.bump(p, 0.5, 1));
      o('ctl', 'look', 1 - c.ramp(p, 0.7, 1));
    } },
    idleA: { dur: 6, fn(p, o, c) { /* a deeper swell, a slight lift of the head, one cycle of the breathing pore */
      o('ctl', 'amp', 0.8 * c.env(p, 0.2, 0.3));
      o('head', 'rx', -0.07 * c.bump(p, 0.15, 0.9)); o('head', 'py', 0.01 * c.bump(p, 0.15, 0.9));
      o('pore', 's', -0.85 * c.bump(p, 0.35, 0.62));
    } },
    idleB: { variants: 2, dur: 3.6, fn(p, o, c) { /* a scanning bout: one stalk lowers to the side and stays while the other keeps upright (posture iii), the lower tentacles tap, one tip quivers at the end */
      const s = c.v === 0 ? 1 : -1, e = c.keys(p, [[0, 0], [0.22, 1], [0.6, 1], [0.86, -0.04], [1, 0]]);
      bendOut(o, s, 0.55 * e); lower(o, s, 0.4 * e); shorten(o, s, 0.12 * e);
      bendOut(o, -s, -0.08 * e);
      o('head', 'rz', -s * 0.06 * e); o('head', 'ry', s * 0.12 * e);
      taps(o, p, 2.4, 0.3 * c.env(p, 0.2, 0.3));
      quiver(o, s, p, 0.74, 0.82, 8, 3.6);
      o('ctl', 'look', 0.6 * e);
    } },
    notice: { dur: 1.8, fn(p, o, c) { /* the head lifts and reaches toward the person, as in loping, and both stalks converge forward at them; down again with weight */
      const e = c.keys(p, [[0, 0], [0.32, 1], [0.66, 1], [0.9, -0.04], [1, 0]]);
      o('head', 'py', 0.1 * e); o('head', 'pz', 0.07 * e); o('head', 'rx', -0.38 * e); o('neck', 'rx', -0.12 * e);
      faceTo(o, e); converge(o, c.keys(p, [[0, 0], [0.4, 1], [0.7, 1], [1, 0]]));
      o('shell', 'rx', -0.05 * e);
      o('ctl', 'look', e);
    } },
    react: { dur: 1.8, fn(p, o, c) { /* the withdrawal reflex: both stalks pull in fast, the head bends down, a hold, then out again slowly; a second tap soon after gets less */
      if (c.amp == null) { c.amp = R.t - SNL.lastReact < 10 ? 0.55 : 1; SNL.lastReact = R.t; }
      const k = c.amp * c.keys(p, [[0, 0], [0.17, 1], [0.55, 1], [0.78, 0.45], [1, 0]]);
      shorten(o, 1, 0.84 * k); shorten(o, -1, 0.84 * k);
      o('stalkL', 'sx', 0.15 * k); o('stalkL', 'sz', 0.15 * k); o('stalkR', 'sx', 0.15 * k); o('stalkR', 'sz', 0.15 * k);
      o('head', 'rx', 0.45 * k); o('head', 'pz', -0.06 * k); o('neck', 'rx', 0.18 * k); o('neck', 'pz', -0.02 * k);
      o('tentL', 'sy', -0.6 * k); o('tentR', 'sy', -0.6 * k);
      o('shell', 'rx', 0.06 * c.bump(p, 0, 0.4) * c.amp);
      o('body', 'sy', -0.02 * k);
      o('ctl', 'look', c.bump(p, 0, 1));
    } },
    talk: { dur: 3, fn(p, o, c) { /* attentive: the head up a little and turned to the person, both stalks forward at them with small independent nods */
      const e = c.env(p, 0.15, 0.25);
      o('head', 'py', 0.05 * e); o('head', 'rx', -0.16 * e); faceTo(o, e);
      lower(o, 1, (0.8 + 0.14 * Math.sin(TAU * 1.5 * p)) * e); lower(o, -1, (0.8 + 0.14 * Math.sin(TAU * 1.5 * p + 1.9)) * e);
      bendOut(o, 1, -0.18 * e); bendOut(o, -1, -0.18 * e);
      o('ctl', 'look', 0.7 * e);
    } },
    lookLeft: { dur: 1.6, fn(p, o, c) { /* the whole head turns toward the page, both stalks bend the same way, the far stalk shortens a little */
      const e = c.keys(p, [[0, 0], [0.4, 1], [0.7, 1], [1, 0]]);
      o('neck', 'ry', -0.45 * e); o('head', 'ry', -0.65 * e);
      o('stalkL', 'rz', 0.3 * e); o('stalkR', 'rz', 0.3 * e); shorten(o, -1, 0.1 * e);
      o('ctl', 'look', e);
    } },
    lookRight: { dur: 1.6, fn(p, o, c) {
      const e = c.keys(p, [[0, 0], [0.4, 1], [0.7, 1], [1, 0]]);
      o('neck', 'ry', 0.25 * e); o('head', 'ry', 0.35 * e);
      o('stalkL', 'rz', -0.3 * e); o('stalkR', 'rz', -0.3 * e); shorten(o, 1, 0.1 * e);
      o('ctl', 'look', e);
    } },
    rest: { dur: 6, fn(p, o, c) { /* the stalks half drawn in, the head down on the ground, the breath slower, the pore cycling */
      const e = c.env(p, 0.25, 0.25);
      shorten(o, 1, 0.45 * e); shorten(o, -1, 0.45 * e); lower(o, 1, 0.1 * e); lower(o, -1, 0.1 * e);
      o('head', 'rx', 0.25 * e); o('head', 'py', -0.03 * e); o('neck', 'rx', 0.1 * e);
      o('tentL', 'sy', -0.4 * e); o('tentR', 'sy', -0.4 * e);
      o('pore', 's', -0.85 * c.bump(p, 0.45, 0.72));
      o('ctl', 'breath', -0.4 * e); o('ctl', 'look', e);
    } },
    dance: { variants: 2, dur: 2.2, fn(p, o, c) { /* "the semaphore", built only from what the real animal does: a startle quiver, the loping head-lift toward the viewer,
                                                       the stalks sweeping outward and back in turn and then converging at the person, the head set down with weight while the shell
                                                       settles, the stalks back upright with a last quiver, and a breath through the pore (research/snail.md, section 3) */
      const s = c.v === 0 ? 1 : -1, D = 2.2;
      /* 0.00-0.25 s: startle: both stalks shorten a fifth and quiver, out of phase */
      const q = c.bump(p, 0, 0.114);
      shorten(o, 1, 0.2 * q); shorten(o, -1, 0.2 * q);
      bendOut(o, 1, 0.1 * Math.sin(TAU * 9 * D * p) * q); bendOut(o, -1, 0.1 * Math.sin(TAU * 9 * D * p + PI) * q);
      /* 0.25-1.60 s: the head lifts and reaches, holds, then sets down with a damped overshoot; the shell tips back and settles */
      const lift = c.keys(p, [[0.114, 0], [0.34, 1], [0.477, 1], [0.62, -0.06], [0.727, 0]]);
      o('head', 'py', 0.2 * lift); o('head', 'pz', 0.15 * lift); o('head', 'rx', -0.44 * lift); o('neck', 'rx', -0.1 * lift);
      o('shell', 'rx', c.keys(p, [[0.114, 0], [0.34, -0.07], [0.5, -0.07], [0.64, 0.035], [0.727, 0]])); o('shell', 'py', 0.02 * lift);
      o('body', 'sy', 0.02 * lift);
      faceTo(o, c.env(p, 0.2, 0.25)); o('head', 'ry', s * 0.26 * c.env(p, 0.2, 0.25));
      /* 0.45-1.30 s: the semaphore: each stalk sweeps outward and back, half a cycle apart, then both come forward-horizontal at the viewer */
      const sw = c.bump(p, 0.2, 0.59);
      bendOut(o, s, (0.61 * Math.max(0, Math.sin(TAU * (p - 0.2) / 0.36)) - 0.17 * Math.max(0, -Math.sin(TAU * (p - 0.2) / 0.36))) * sw);
      bendOut(o, -s, (0.61 * Math.max(0, Math.sin(TAU * (p - 0.2) / 0.36 + PI)) - 0.17 * Math.max(0, -Math.sin(TAU * (p - 0.2) / 0.36 + PI))) * sw);
      const conv = c.keys(p, [[0.2, 0], [0.59, 1], [0.7, 1], [0.864, 0]]);
      lower(o, 1, 1.05 * conv); lower(o, -1, 1.05 * conv); bendOut(o, 1, -0.2 * conv); bendOut(o, -1, -0.2 * conv);
      /* 1.30-1.90 s: the stalks re-extend a little past their length and settle; one tip gives a last quiver */
      const ext = c.keys(p, [[0.59, 0], [0.72, -0.06], [0.864, 0]]);
      shorten(o, 1, ext); shorten(o, -1, ext);
      quiver(o, s, p, 0.75, 0.864, 8, D);
      /* 1.60-2.20 s: a breath through the pore while everything settles */
      o('pore', 's', -0.85 * c.bump(p, 0.727, 1));
      taps(o, p, 2, 0.2 * c.env(p, 0.3, 0.3));
      o('ctl', 'look', c.env(p, 0.1, 0.2));
    } },
  };
  K.finish(R);
  /* for the lab: where the shell and the aperture ended up, in the sculpting space */
  R.notes = { shell: SHELL, apertureCentre: apC, apertureNormal: apN, apexAt: toSculpt(extras.apex || [0, 0.45, 0]) };
  return R;
}

export default {
  id: 'snail',
  name: 'Garden snail',
  latin: 'Cornu aspersum',
  rests: 'floor',
  build: (THREE, kit) => buildSnail(THREE, kit),
  update: (rig, dt, state) => rig.kit.update(rig, dt, state),
  play: (rig, clip, variant) => rig.kit.play(rig, clip, variant),
  rest: (rig) => rig.kit.rest(rig),
};
