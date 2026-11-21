/*
  The Civic Archive companion: the Adélie penguin (Pygoscelis adeliae). The default companion.

  Sculpted in code on the companions' realism kit (kit.js) from the measurements and field notes in
  research/penguin.md (Levick 1914; Chappell & Souza 1988; Griffin & Kram 2000; Willener et al. 2015, 2016; Raikow et al.
  1988; Ainley 2002 via ADW). No model was found under the kit's rules, so nothing is loaded from anywhere.

  The animal. One unit is the standing height (about 70 cm). A small round head (skull about 0.13 H) with a steep
  forehead sits in a feathered collar on a stocky trunk 0.36 H across; the short black bill is feathered to half its
  length and only the tip shows; the eye is set in the side of the head inside the crisp white ring that is in fact the
  bird's bare eyelids, so a blink is a white flash and the whites of the eye show when it rolls them down (Levick); the
  flippers are stiff paddles that move only at the shoulder (Raikow), black above with a white trailing edge and white
  beneath, hanging 18 degrees off the body with the tips at mid-belly; the long stiff tail reaches the ground when the
  bird leans back on its heels; the feet are pink with black claws, toed out, the legs hidden in the belly feathers.
  Body, flippers and tail are one signed distance field surfaced as one mesh that bends over a skeleton (hips, neck,
  head, two shoulders, tail), dressed in short dense feather shells with a satin sheen, the black glossier than the
  white; the bill is horn with a clearcoat, the lower mandible on its own joint; the eyes are wet with a glint.

  How it moves (every number from the research notes, estimates where the notes say so):
    breathing   a quick breath then stillness, about one in 7 to 8 s (8 a minute at rest), never a steady heave; after a
                hop, a dance or the walk in it pants at about 25 a minute for a while and calms down again
    blinks      the kit's irregular 2.5 to 6 s with a white lid; two thirds of blinks land on a head turn
    looking     the one-eyed inspection: the head yaws to present an eye to the pointer in a 0.15 s snap with a 10 %
                overshoot and a small forward poke, holds, and now and then switches to the other eye (Levick); the body
                follows by 15 %; then it looks back at the page
    waddle      2.2 steps a second, a roll of 12 degrees over the planted foot, the body highest at full roll (Griffin &
                Kram), the head counter-rolling, the flippers swinging with the opposite foot, the stiff tail sweeping
    dance       the ecstatic display: up on its toes, the neck opens and the bill points at the sky and parts, the flippers
                rise to horizontal and beat in time with three breast heaves, the eyes roll down so the whites show, the
                feathers lift; then the bill comes down, a quick 5.5 Hz head-shake, a white blink, and it settles
    the rest    head-shake and ruffle, bill-to-axilla preen, the flipper stretch with its shiver, the sleepy
                ruffle-close-smooth, the flap-and-hop, the two-eyed stare

  export default { id, name, latin, rests, build(THREE, kit) -> rig, update(rig, dt, state), play(rig, clip) -> seconds, rest(rig) }
    rig.root   1 unit = the body's height, facing +z toward the viewer, feet at y = 0
    rig.frame  the box, in root units, a camera should keep in view: { x: [min, max], y: [min, max] }
    clips      arrive, idleA, idleB (4 versions), notice, react, talk, lookLeft, lookRight, rest, dance; every clip ends
               exactly on the rest pose.
*/

const FURLEN = 0.0048;      /* the pile of the body feathers: short, dense, lying flat */

function buildPenguin(THREE, K) {
  if (!K || !K.rig) throw new Error('the penguin needs the companions kit: build(THREE, kit)');
  const { sd, surf, strip, circle, rgb, mixc, fbm, sst, lerp, clamp } = K;
  const TAU = K.TAU;
  const R = K.rig({
    id: 'penguin', yaw: -0.3, frame: { x: [-0.56, 0.56], y: [-0.04, 1.1] }, fov: 34,
    breath: 0.135,                               /* one breath in 7.4 s; the pulse shape is in life() below */
    look: { yaw: 0, pitch: 0 },                  /* the kit's own attention is off: the one-eyed inspection below replaces it */
    idles: ['idleA', 'idleB', 'idleB', 'notice'],
  });
  const NECK_YAW = -0.12, HEAD_YAW = -0.30;      /* the head rests turned 24 degrees past the body: one eye to the reader */
  const FACE = 0.3 - NECK_YAW - HEAD_YAW;        /* the turn that brings both eyes onto the reader */

  /* colours from the species sheet (black, white, greys, the pink of the feet; a brown gape, never red) */
  const INK = rgb(0x121315), INK2 = rgb(0x26272a), SNOW = rgb(0xf4f3ef), SNOW2 = rgb(0xe3e1d9), BUFF = rgb(0xe9e3d6);
  const BILL = rgb(0x151313), BILL2 = rgb(0x3b2b24), FOOT = rgb(0xd9a8a0), FOOT2 = rgb(0xb5827b), CLAW = rgb(0x2a2220);

  /* ---------- the sculpt (sculpting space: feet at y = 0, the bird faces +z) ---------- */
  /* the head: a small round skull with a high crown, the feathered base of the bill, a full throat */
  const skull = sd.egg([0, 0.905, 0.03], [0.077, 0.08, 0.09]);
  const crown = sd.egg([0, 0.942, -0.012], [0.052, 0.052, 0.066]);      /* the slight peak at the back of the crown */
  const snout = sd.egg([0, 0.885, 0.112], [0.046, 0.04, 0.052]);
  const throat = sd.egg([0, 0.80, 0.06], [0.06, 0.07, 0.07]);
  const nape = sd.egg([0, 0.79, 0.005], [0.07, 0.075, 0.08]);
  const head = sd.add(0.04, skull, crown, snout);
  const neckS = sd.add(0.06, head, nape, throat);
  /* the trunk: shoulders, a full belly, the rump */
  const chest = sd.egg([0, 0.625, 0.02], [0.155, 0.145, 0.148]);
  const torso = sd.egg([0, 0.43, -0.012], [0.182, 0.33, 0.172]);
  const belly = sd.egg([0, 0.29, 0.03], [0.172, 0.245, 0.165]);
  const rump = sd.egg([0, 0.3, -0.07], [0.158, 0.25, 0.15]);
  const trunk = sd.add(0.08, chest, torso, belly, rump);
  const full = sd.add(0.07, trunk, neckS);

  /* the flippers: one stiff paddle each, hung at the shoulder (at the body's surface), 0.27 H long, 0.074 H wide at the
     base, tapering, 18 degrees off the body and angled a little back */
  const FLIP_LEN = 0.255;
  const flip = (s) => {
    const F = sd.frame([s * 0.153, 0.65, -0.005], [0.05, s * 0.22, s * 0.32]);
    const blade = sd.xf(sd.limb([0, 0.012, 0], [0, -FLIP_LEN, -0.015], 0.037, 0.019), [0, 0, 0], null, [0.36, 1, 1]);
    return { F, f: F.place(blade), s };
  };
  const FL = flip(1), FR = flip(-1);

  /* the tail: a stiff wedge of rectrices reaching down and back to the ground */
  const TAIL_DIR = [0, -Math.sin(0.72), -Math.cos(0.72)];
  const tailS = sd.xf(sd.limb([0, 0, 0], [0, 0, -0.2], 0.05, 0.024), [0, 0.17, -0.165], [-0.72, 0, 0], [1, 0.3, 1]);

  /* the feet: three webbed toes forward with black claws, toed out 12 degrees, the tarsus up into the belly feathers */
  const foot = (s) => {
    const hx = s * 0.075, parts = [], claws = [];
    for (const a of [-0.36, 0, 0.36]) {
      const ang = a + s * 0.2, dx = Math.sin(ang), dz = Math.cos(ang);
      parts.push(sd.limb([hx, 0.019, 0.03], [hx + dx * 0.088, 0.013, 0.03 + dz * 0.088], 0.02, 0.012));
      claws.push(sd.limb([hx + dx * 0.092, 0.012, 0.03 + dz * 0.092], [hx + dx * 0.115, 0.004, 0.03 + dz * 0.115], 0.0085, 0.003));
    }
    parts.push(sd.egg([hx + s * 0.012, 0.009, 0.08], [0.052, 0.009, 0.046]));
    parts.push(sd.limb([hx, 0.022, 0.028], [hx * 0.9, 0.11, -0.01], 0.028, 0.034));
    const clawS = sd.add(0, ...claws);
    return { f: sd.add(0.014, sd.add(0.016, ...parts), clawS), claw: clawS };
  };
  const FtL = foot(1), FtR = foot(-1);

  /* the bill: the upper mandible with a hooked tip, rigid on the head; the lower on its own joint */
  const billU = sd.xf(sd.add(0.01,
    sd.limb([0, 0.883, 0.125], [0, 0.877, 0.222], 0.027, 0.011),
    sd.limb([0, 0.884, 0.192], [0, 0.866, 0.228], 0.012, 0.005)), [0, 0, 0], null, [0.85, 1, 1]);
  const billL = sd.xf(sd.limb([0, 0.867, 0.125], [0, 0.863, 0.215], 0.02, 0.007), [0, 0, 0], null, [0.8, 1, 1]);

  /* body, flippers and tail become one skinned surface; everything together shades the crevices */
  const bodyAll = sd.add(0.02, full, FL.f, FR.f, tailS);
  const all = sd.min(bodyAll, billU, billL, FtL.f, FtR.f);

  /* ---------- the plumage ---------- */
  /* which part a surface point belongs to */
  const partOf = (x, y, z) => {
    const b = full(x, y, z);
    if (Math.abs(x) > 0.13 && y < 0.72) {
      const F = x > 0 ? FL : FR;
      if (F.f(x, y, z) < b - 0.003) return F;
    }
    if (z < -0.1 && y < 0.26 && tailS(x, y, z) < b - 0.003) return 'tail';
    return 'body';
  };
  /* the white front: it begins under the black throat in a clean line that dips toward the shoulders, and wraps round
     the flanks further the lower it goes; the head, nape, back, rump and tail are black */
  const frontWhite = (x, y, z) => {
    const a = Math.abs(Math.atan2(x, z + 0.01));
    const top = 0.715 - 0.06 * sst(0.5, 1.4, a);
    const side = 1.34 - 0.12 * sst(0.62, 0.22, y);
    return sst(-0.03, 0.03, side - a) * sst(-0.009, 0.009, top - y);
  };
  /* the flipper: black above with a thin white trailing edge; white beneath with a black tip and leading edge */
  const flipWhite = (F, x, y, z) => {
    const l = F.F.loc(x, y, z), t = clamp(-l[1] / FLIP_LEN, 0, 1), r = lerp(0.037, 0.019, t);
    if (l[0] * F.s > 0) return sst(-(r - 0.02), -(r - 0.005), l[2]) * sst(0.88, 0.78, t);
    return sst(0.86, 0.78, t) * sst(r - 0.004, r - 0.014, l[2]);
  };
  const whiteOf = (x, y, z) => {
    const P = partOf(x, y, z);
    if (P === 'tail') return 0;
    if (P !== 'body') return flipWhite(P, x, y, z);
    return frontWhite(x, y, z);
  };
  const paintBody = (x, y, z) => {
    const w = whiteOf(x, y, z), n = fbm(x * 70, y * 70, z * 70, 2), n2 = fbm(x * 18 + 3, y * 18, z * 18, 2);
    const blk = mixc(INK, INK2, 0.25 + n * 0.55 + n2 * 0.2);
    const wht = mixc(SNOW, mixc(SNOW2, BUFF, 0.5), 0.1 + n * 0.35 + n2 * 0.15 + 0.35 * sst(0.3, 0.06, y));
    return mixc(blk, wht, w);
  };
  /* the black feathers are glossier than the white (per-vertex roughness, clearcoat and sheen multipliers) */
  const matAt = (x, y, z) => { const w = whiteOf(x, y, z); return [lerp(0.9, 1.15, w), lerp(1.2, 0.3, w), lerp(1.0, 0.9, w)]; };

  /* where the eyes sit: in the sides of the head, yawed 60 degrees from the bill and a little up, found on the surface
     before the groom so no feather crosses them */
  const HC = [0, 0.915, 0.04], EYES = [];
  for (const s of [1, -1]) {
    const yaw = s * 1.05, pit = 0.1;
    const d = [Math.sin(yaw) * Math.cos(pit), Math.sin(pit), Math.cos(yaw) * Math.cos(pit)];
    EYES.push({ s, d, sp: K.hit(full, HC, d) });
  }
  const BILL_ROOT = [0, 0.878, 0.14];
  const nearEye = (x, y, z, r0, r1) => { let k = 1; for (const E of EYES) k *= sst(r0, r1, Math.hypot(x - E.sp[0], y - E.sp[1], z - E.sp[2])); return k; };
  const nearBill = (x, y, z, r0, r1) => sst(r0, r1, Math.hypot(x - BILL_ROOT[0], y - BILL_ROOT[1], z - BILL_ROOT[2]));

  /* the groom: short feathers lying flat, combed down the body and back along the head, a little longer on the flanks
     and the rump, nearly none on the flippers, none across the eye-rings or the base of the bill, where the short
     feathers point forward over the bill */
  const groom = (x, y, z) => {
    const hd = sst(0.78, 0.86, y), a = Math.abs(Math.atan2(x, z + 0.01));
    const flank = sst(0.7, 1.2, a) * (1 - hd) * sst(0.75, 0.55, y);
    let len = lerp(1, 0.6, hd) * (0.85 + 0.3 * flank + 0.35 * sst(0.35, 0.1, y) * sst(0.6, 1.6, a));
    len *= nearEye(x, y, z, 0.022, 0.04) * nearBill(x, y, z, 0.05, 0.1);
    const P = partOf(x, y, z);
    if (P !== 'body' && P !== 'tail') len *= 0.3;
    if (P === 'tail') len *= 0.5;
    const sn = 1 - nearBill(x, y, z, 0.05, 0.09);
    const cx = -0.12 * x, cy = -0.95 + 0.5 * hd, cz = -0.5 * hd - 0.1 + 1.2 * sn;
    return [len, 1, cx, cy, cz];
  };

  /* ---------- materials ---------- */
  /* plumage: a satin sheen (dark, so black stays black), a little clearcoat where the feathers lie tight, no gloss */
  const feather = K.physical({ rough: 0.62, sheen: 0.6, sheenRough: 0.5, sheenColor: 0x6a6a6e, spec: 0.4, clearcoat: 0.12, ccRough: 0.35, name: 'penguin-feather' });
  const horn = K.physical({ rough: 0.3, clearcoat: 0.7, ccRough: 0.15, spec: 0.7, name: 'penguin-bill' });
  const skinM = K.physical({ rough: 0.5, clearcoat: 0.25, ccRough: 0.35, sheen: 0.15, spec: 0.5, name: 'penguin-foot' });
  const ringM = K.physical({ rough: 0.62, sheen: 0.25, spec: 0.35, clearcoat: 0.1, name: 'penguin-ring' });

  /* ---------- the skeleton ---------- */
  K.joint(R, 'body', 'pose', [0, 0.07, 0]);                 /* the hips: the waddle rolls here */
  K.joint(R, 'neck', 'body', [0, 0.70, 0.0]);               /* the base of the neck */
  K.joint(R, 'head', 'neck', [0, 0.84, 0.02]);              /* the atlas */
  K.joint(R, 'jaw', 'head', [0, 0.872, 0.13]);
  K.joint(R, 'flipL', 'body', [0.153, 0.65, -0.005]);
  K.joint(R, 'flipR', 'body', [-0.153, 0.65, -0.005]);
  K.joint(R, 'tail', 'body', [0, 0.17, -0.165]);
  K.joint(R, 'footL', 'pose', [0.075, 0.03, 0.035]);
  K.joint(R, 'footR', 'pose', [-0.075, 0.03, 0.035]);
  K.joint(R, 'aux', 'body', [0, 0.5, 0]);                   /* carries nothing: its channels ask for the eye roll (rx), the ruffle (py) and exertion (px) */
  K.limit(R, 'head', { ry: [-1.3, 1.3], rx: [-1.5, 0.9], rz: [-0.6, 0.6] });
  K.limit(R, 'neck', { ry: [-0.6, 0.6], rx: [-0.8, 0.6] });
  K.limit(R, 'jaw', { rx: [0, 0.6] });

  /* the skinned body: weights by distance to each bone; the body never reaches the face, the neck never reaches the eyes
     or the bill, the head never reaches the chest; the flippers and the tail only outside the trunk */
  const away = (x, y, z) => sst(-0.004, 0.03, full(x, y, z));
  const bodyGeo = surf(bodyAll, [-0.33, -0.02, -0.37, 0.33, 1.0, 0.27], 0.0105, paintBody, { ao: all, groom, matAt });
  const bodyMesh = K.skin(R, bodyGeo, [
    { j: 'body', a: [0, 0.08, 0], b: [0, 0.66, 0], r: 0.17, only: (x, y) => sst(0.80, 0.72, y) },
    { j: 'neck', a: [0, 0.70, 0], b: [0, 0.80, 0.01], r: 0.1, only: (x, y, z) => sst(0.86, 0.80, y) * nearEye(x, y, z, 0.062, 0.075) * nearBill(x, y, z, 0.085, 0.1) },
    { j: 'head', a: [0, 0.84, 0.02], b: [0, 0.96, 0.05], r: 0.12, only: (x, y) => sst(0.70, 0.80, y) },
    { j: 'flipL', a: [0.155, 0.65, -0.005], b: [0.228, 0.41, -0.049], r: 0.034, only: away },
    { j: 'flipR', a: [-0.155, 0.65, -0.005], b: [-0.228, 0.41, -0.049], r: 0.034, only: away },
    { j: 'tail', a: [0, 0.17, -0.17], b: [0, 0.045, -0.31], r: 0.04, only: away },
  ], feather, { smooth: 3, name: 'penguin-body' });
  K.fur(R, bodyMesh, { len: FURLEN, dens: 230, thin: 0.9, root: 0.92, clump: 0.25, comb: 1.1, droop: 0.02, min: 0.55 });

  /* the bill */
  const paintBill = (x, y, z) => mixc(BILL2, BILL, sst(0.13, 0.17, z) * 0.85 + 0.15);
  K.put(R, 'head', surf(billU, [-0.03, 0.85, 0.12, 0.03, 0.915, 0.25], 0.005, paintBill, { ao: all }), horn);
  K.put(R, 'jaw', surf(billL, [-0.025, 0.84, 0.12, 0.025, 0.89, 0.24], 0.005, paintBill, { ao: all }), horn);

  /* the feet */
  const paintFoot = (Ft) => (x, y, z) => {
    if (Ft.claw(x, y, z) < 0.004) return CLAW;
    return mixc(FOOT, FOOT2, sst(0.012, 0.0, y) * 0.5 + fbm(x * 60, y * 60, z * 60, 2) * 0.35);
  };
  K.put(R, 'footL', surf(FtL.f, [0.0, -0.01, -0.04, 0.2, 0.15, 0.17], 0.006, paintFoot(FtL), { ao: all }), skinM);
  K.put(R, 'footR', surf(FtR.f, [-0.2, -0.01, -0.04, 0.0, 0.15, 0.17], 0.006, paintFoot(FtR), { ao: all }), skinM);

  /* the eyes: brown iris, a white sclera that shows when the eye rolls down, white lids, each in the white ring of bare
     skin that is the Adélie's eyelid */
  R.eyeBalls = [];
  for (const E of EYES) {
    const { s, d, sp } = E;
    /* the eye is 0.028 H across and nearly all iris (dark brown); the white is the thin ring of lid around it, which
       widens to a white disc when the lids shut and shows a white crescent above the iris when the eye rolls down */
    const r = 0.014, c = [sp[0] - d[0] * r * 0.45, sp[1] - d[1] * r * 0.45, sp[2] - d[2] * r * 0.45];
    const name = s > 0 ? 'eyeL' : 'eyeR';
    const j = K.eye(R, name, 'head', c, d, r, {
      iris: 0x3a2616, iris2: 0x5c3b24, pupil: 0.4, irisAngle: 1.25, sclera: 0xe7e2d8, limbal: 0x1a100a,
      lid: SNOW, lidMat: { rough: 0.6, sheen: 0.35, spec: 0.35, name: name + '-lid' }, lidScale: 1.08, open: -1.0, shut: 1.55, glint: 0.3, lowerShare: 0.3, gloss: 0.7, wet: 0.4,
    });
    const ball = j.children.find((m) => m.name === name + '-mesh');
    if (ball) R.eyeBalls.push(ball);
    const ring = strip(full, circle(sp, d, 0.0175, 40), 0.0058, SNOW, { closed: true, lift: 0.0022 });
    K.put(R, 'head', ring, ringM);
  }

  /* secondary motion: the tail swings after a hop or a turn; the flippers follow a flap through; the head carries weight */
  K.spring(R, 'tail', { ch: 'rx', k: 110, c: 10, gain: 0.05, dir: TAIL_DIR, lim: [-0.3, 0.3] });
  K.spring(R, 'flipL', { ch: 'rz', k: 220, c: 16, gain: 0.012, dir: [0.3, -1, 0], lim: [-0.4, 0.4] });
  K.spring(R, 'flipR', { ch: 'rz', k: 220, c: 16, gain: 0.012, dir: [-0.3, -1, 0], lim: [-0.4, 0.4] });
  K.spring(R, 'head', { ch: 'rx', k: 380, c: 26, gain: 0.025, dir: [0, 1, 0.15], lim: [-0.25, 0.25] });

  /* ---------- what runs every frame ---------- */
  const shellMats = [];
  for (const G of R.furs) for (const sh of G.shells) shellMats.push(sh.material);
  const setPile = (mult) => { for (const m of shellMats) m.userData.u.uFurLen.value = FURLEN * mult; };
  /* a turn of the head is three quarters head and one quarter neck, so the neck bends into it */
  const turn = (o, dy, dx) => {
    if (dy) { o('head', 'ry', 0.75 * dy); o('neck', 'ry', 0.25 * dy); }
    if (dx) { o('head', 'rx', 0.7 * dx); o('neck', 'rx', 0.3 * dx); }
  };
  /* the one-eyed inspection and the breathing's after-effects live on the rig */
  R.gz = { y: 0, vy: 0, p: 0, vp: 0, by: 0, vby: 0, ty: 0, tp: 0, aim: 0, side: 0, px: null, py: null, until: 0, hold: 0, snapT: 9, poke: 0 };
  R.puff = 0; R.ruffle = 0;
  const SWITCH = 1.1;      /* the turn that presents the other eye to the same spot */
  const resetGaze = () => { const G = R.gz; G.y = G.vy = G.p = G.vp = G.by = G.vby = G.ty = G.tp = G.aim = 0; G.side = 0; G.px = G.py = null; G.until = 0; G.hold = 0; G.snapT = 9; G.poke = 0; };
  R.pg = {
    /* before the kit's own update: the pointer becomes a target for the head, snapped at with one eye */
    step(dt, st) {
      if (st && st.motion && st.motion !== 'on') { resetGaze(); R.puff = 0; return; }
      dt = dt > 0 ? Math.min(dt, 0.1) : 0;
      R.puff = Math.max(0, R.puff - dt / 9);
      if (R.puff > 0) R.phase += dt * TAU * 0.28 * R.puff;      /* out of breath: the breathing runs faster for a while */
      const G = R.gz, P = st && st.pointer;
      /* a new aim far from the old one is a snap (a poke, and two thirds of the time a blink); a small one is followed smoothly */
      /* a blink already due soon lands on the turn instead (Yorzinski 2020: two thirds of blinks ride on a head saccade); the rate stays the kit's */
      const blinkNow = () => { if (R.blinkT < 0 && R.nextBlink - R.t < 1.6 && R.rnd() < 0.65) R.nextBlink = R.t + 0.02; };
      const snap = (ty) => { const big = G.px === null || Math.abs(ty - G.ty) > 0.3; G.ty = ty; if (big) { G.snapT = 0; G.hold = 0.7 + R.rnd() * 0.7; blinkNow(); } };
      if (P && (G.px === null || Math.abs(P.x - G.px) + Math.abs(P.y - G.py) > 0.04)) {
        G.aim = clamp(P.x * 0.6, -1, 1) * 0.8;
        G.tp = -clamp(P.y * 0.6, -1, 1) * 0.35;
        snap(G.aim + (G.side ? SWITCH : 0));
        G.px = P.x; G.py = P.y; G.until = R.t + 1.6 + R.rnd() * 2.0;
      } else if (P && R.t < G.until) {
        G.hold -= dt;
        if (G.hold <= 0) {      /* a near thing is looked at with one eye, then the other, with little jerks (Levick) */
          if (R.rnd() < 0.5) G.side = 1 - G.side;
          G.ty = G.aim + (G.side ? SWITCH : 0) + (R.rnd() - 0.5) * 0.16;
          G.snapT = 0; G.hold = 0.7 + R.rnd() * 0.7; blinkNow();
        }
      }
      if (!P) { G.px = null; G.py = null; }
      if (R.t > G.until && (G.ty !== 0 || G.tp !== 0)) { G.ty = 0; G.tp = 0; G.side = 0; G.snapT = 9; }
      const back = G.ty === 0 && G.tp === 0;
      const w = back ? 7 : 28, z = back ? 1 : 0.55, wp = back ? 7 : 12, wb = 8;
      G.vy += (w * w * (G.ty - G.y) - 2 * z * w * G.vy) * dt; G.y += G.vy * dt;
      G.vp += (wp * wp * (G.tp - G.p) - 2 * wp * G.vp) * dt; G.p += G.vp * dt;
      G.vby += (wb * wb * (0.15 * G.y - G.by) - 2 * wb * G.vby) * dt; G.by += G.vby * dt;
      G.snapT += dt;
      const u = G.snapT / 0.1;
      G.poke = u < 8 ? 0.035 * u * Math.exp(1 - u) : 0;
    },
    reset() { resetGaze(); R.puff = 0; R.ruffle = 0; setPile(1); for (const e of R.eyeBalls) e.rotation.x = 0; },
  };
  R.spec.life = (o, L) => {
    const G = R.gz, k = 1 - Math.min(1, R.ctl.look), puff = L.still ? 0 : R.puff;
    /* breathing: the kit's slow sine becomes a quick breath (the top fifth of the wave) and a long hold with a faint
       swell; panting widens the breath */
    const b = L.b, q = sst(0.78 - 0.5 * puff, 1, b);
    const sw = (0.02 + 0.012 * puff) * q + 0.003 * b;
    o('body', 'sx', sw); o('body', 'sz', 0.8 * sw); o('body', 'sy', 0.2 * sw);
    o('neck', 'sx', 0.5 * sw); o('neck', 'sz', 0.9 * sw + 0.012 * puff * q);
    o('head', 'py', 0.004 * q); o('head', 'rx', -0.015 * q);
    o('flipL', 'rz', 0.025 * q); o('flipR', 'rz', -0.025 * q);
    o('tail', 'rx', -0.012 * q);
    if (!L.still) {
      turn(o, G.y * k, 0);
      o('head', 'rx', (G.p + 3.2 * G.poke) * k); o('head', 'rz', -0.08 * G.y * k);
      o('neck', 'pz', G.poke * k); o('neck', 'py', -0.25 * G.poke * k);
      o('body', 'ry', G.by * k);
    }
    const ax = R.acc.aux;      /* what the clips asked of the eyes and the plumage this frame */
    if (ax) {
      if (ax[0] > R.puff) R.puff = Math.min(1, ax[0]);
      for (const e of R.eyeBalls) e.rotation.x = ax[3];
      if (ax[1] !== R.ruffle) { R.ruffle = ax[1]; setPile(1 + 0.7 * ax[1]); }
    }
  };

  /* ---------- the clips ---------- */
  /* the way in: 1.2 H at a nearly steady pace, stopping softly at 0.8 of the clip (6 quick steps of about 0.25 H) */
  const xArrive = (p) => { const u = Math.min(1, p / 0.8); return 1.2 * Math.pow(1 - u, 1.35); };
  const STEPS = 3;
  /* the waddle at stride phase ph (0 when the right foot lands): a roll of amp over the planted foot, the hips over it,
     the body highest at full roll, the head counter-rolling, the pelvis yawing, the flippers swinging with the opposite
     foot, the tail sweeping */
  const waddle = (o, ph, g, amp) => {
    const s = Math.sin(ph - 0.43);
    o('body', 'rz', amp * s * g); o('body', 'px', -0.03 * s * g); o('body', 'py', 0.015 * Math.abs(s) * g);
    o('head', 'rz', -0.4 * amp * s * g);
    o('body', 'ry', -0.1 * Math.sin(ph - 3.53) * g);
    o('flipL', 'rx', -0.22 * Math.sin(ph - 3.53) * g); o('flipR', 'rx', 0.22 * Math.sin(ph - 3.53) * g);
    o('tail', 'rz', -0.08 * s * g);
    o('head', 'rx', 0.06 * Math.pow(Math.abs(Math.cos(ph - 0.35)), 6) * g);      /* a small nod at each footfall */
  };
  R.clips = {
    arrive: { dur: 1.8, fn(p, o, c) { /* waddles in from the right at 2.2 steps a second, turns to the page, settles */
      const g = 1 - c.ramp(p, 0.6, 0.84), yawTurn = -1.0 * (1 - c.ramp(p, 0.5, 0.9)), yawAt = -0.3 + yawTurn;
      o('mover', 'px', xArrive(p));
      o('pose', 'ry', yawTurn);
      const ow = (n, ch, v) => { if (ch === 'px') { o(n, 'px', v * Math.cos(yawAt)); o(n, 'pz', v * Math.sin(yawAt)); } else o(n, ch, v); };
      c.walk(ow, p, { xOf: xArrive, steps: STEPS, feet: ['footR', 'footL'], lift: 0.03, duty: 0.4, stride: 0.25, rx: 3 });
      waddle(o, c.TAU * STEPS * p, g, 0.21);
      o('body', 'rx', 0.1 * g); o('head', 'rx', -0.1 * g);                    /* leans into the walk, head level */
      o('flipL', 'rz', 0.15 * g); o('flipR', 'rz', -0.15 * g);                /* flippers out for balance */
      const ahead = c.keys(p, [[0, 1], [0.84, 1], [0.9, -0.1], [0.96, 0.02], [1, 0]]);      /* both eyes ahead on the march, then the one-eyed snap */
      turn(o, -(NECK_YAW + HEAD_YAW) * ahead, 0);
      o('neck', 'pz', 0.03 * c.bump(p, 0.85, 0.97)); o('ctl', 'lid', c.bump(p, 0.86, 0.95));
      const st = c.bump(p, 0.84, 1);
      o('body', 'rz', 0.07 * Math.sin((c.TAU * 2 * (p - 0.84)) / 0.16) * st);      /* two damped roll cycles at the stop */
      o('body', 'rx', -0.06 * st);                                                /* the weight goes back onto the heels */
      o('ctl', 'look', 1 - c.ramp(p, 0.9, 1)); o('aux', 'px', 1);
    } },
    idleA: { dur: 5, fn(p, o, c) { /* a slow shift of weight, a deeper breath, a glance about */
      const e = c.env(p, 0.2, 0.3), s = Math.sin(c.TAU * p) * e;
      o('body', 'rz', 0.05 * s); o('body', 'px', -0.01 * s); o('head', 'rz', -0.04 * s);
      o('ctl', 'amp', 0.8 * c.bump(p, 0.1, 0.8));
      turn(o, 0.15 * c.bump(p, 0.45, 0.75), 0);
    } },
    idleB: { variants: 4, dur: (v) => [1.6, 3.2, 2.2, 2.6][v], fn(p, o, c) {
      const dur = [1.6, 3.2, 2.2, 2.6][c.v], ts = p * dur;
      if (c.v === 0) { /* the head-shake that flicks brine off the bill, then a ruffle and a smooth */
        const sh = c.bump(p, 0.08, 0.33);
        o('head', 'ry', 0.4 * Math.sin(c.TAU * 5.5 * ts) * sh); o('head', 'rz', 0.12 * Math.sin(c.TAU * 5.5 * ts - 1.57) * sh);
        o('body', 's', 0.015 * c.bump(p, 0.3, 0.95)); o('aux', 'py', 0.8 * c.bump(p, 0.3, 0.95));
        o('flipL', 'rz', 0.09 * c.bump(p, 0.1, 0.5)); o('flipR', 'rz', -0.09 * c.bump(p, 0.1, 0.5));
      } else if (c.v === 1) { /* bill-to-axilla preening: a flipper lifts, the head turns under it and nibbles */
        const s = c.r < 0.5 ? 1 : -1, e = c.keys(p, [[0, 0], [0.15, 1], [0.8, 1], [1, 0]]);
        o(s > 0 ? 'flipL' : 'flipR', 'rz', s * 1.1 * e); o(s > 0 ? 'flipL' : 'flipR', 'rx', -0.15 * e);
        if (s > 0) { o('head', 'ry', 1.3 * e); o('neck', 'ry', 0.6 * e); } else { o('head', 'ry', -0.9 * e); o('neck', 'ry', -0.3 * e); }
        o('head', 'rx', 0.7 * e); o('neck', 'rx', 0.2 * e); o('head', 'rz', s * 0.15 * e);
        const nib = c.bump(p, 0.25, 0.75);
        o('head', 'rx', 0.08 * Math.sin(c.TAU * 7 * ts) * nib); o('jaw', 'rx', 0.15 * (0.5 + 0.5 * Math.sin(c.TAU * 7 * ts)) * nib);
        o('body', 'rz', -s * 0.05 * e); o('body', 'ry', s * 0.08 * e);
        o('ctl', 'look', e);
      } else if (c.v === 2) { /* the stretch: both flippers back and up, neck up, a shiver at the end */
        const e = c.keys(p, [[0, 0], [0.25, 1], [0.6, 1], [0.86, -0.06], [1, 0]]);
        o('flipL', 'rz', 0.8 * e); o('flipR', 'rz', -0.8 * e); o('flipL', 'rx', 0.5 * e); o('flipR', 'rx', 0.5 * e);
        o('neck', 'py', 0.03 * e); o('head', 'rx', -0.25 * e); o('body', 'rx', -0.05 * e);
        const sh = 0.06 * Math.sin(c.TAU * 8 * ts) * c.bump(p, 0.6, 0.78);
        o('flipL', 'rz', sh); o('flipR', 'rz', -sh);
        o('ctl', 'look', 0.5 * e);
      } else { /* sleepy: the feathers lift, the white lids close for most of a second, then it smooths itself out */
        const e = c.keys(p, [[0, 0], [0.15, 1], [0.75, 1], [1, 0]]);
        o('aux', 'py', e); o('body', 's', 0.02 * e);
        o('ctl', 'lid', c.keys(p, [[0, 0], [0.2, 0], [0.3, 1], [0.62, 1], [0.72, 0], [1, 0]]));
        o('head', 'py', -0.015 * e); o('head', 'rx', 0.15 * e); o('ctl', 'breath', -0.4 * e);
        o('ctl', 'look', e);
      }
    } },
    notice: { dur: 1.2, fn(p, o, c) { /* snaps round to look at the person with both eyes, a poke of the head, a blink */
      const e = c.keys(p, [[0, 0], [0.12, 1.1], [0.2, 1], [0.68, 1], [0.9, 0], [1, 0]]);
      turn(o, FACE * e, 0);
      o('neck', 'pz', 0.04 * c.bump(p, 0.02, 0.35)); o('head', 'rx', 0.14 * c.bump(p, 0.02, 0.35) - 0.05 * e);
      o('body', 'ry', 0.15 * FACE * e);
      o('ctl', 'lid', c.bump(p, 0.08, 0.3));
      o('ctl', 'look', c.env(p, 0.05, 0.1));
    } },
    react: { dur: 1.5, fn(p, o, c) { /* the flipper-flap and the two-footed hop */
      const ts = p * 1.5;
      const crouch = c.keys(p, [[0, 0], [0.1, 1], [0.17, 0], [1, 0]]);
      o('body', 'py', -0.05 * crouch); o('flipL', 'rx', 0.5 * crouch); o('flipR', 'rx', 0.5 * crouch); o('body', 'rx', 0.1 * crouch);
      const air = c.hop(p, 0.17, 0.37);
      o('mover', 'py', 0.15 * air);
      o('footL', 'rx', 0.3 * air); o('footR', 'rx', 0.3 * air);
      const fling = c.bump(p, 0.12, 0.42);
      o('flipL', 'rz', 1.4 * fling); o('flipR', 'rz', -1.4 * fling);
      o('neck', 'py', 0.05 * c.bump(p, 0.15, 0.45)); o('head', 'rx', -0.2 * c.bump(p, 0.15, 0.45));
      o('body', 'py', -0.04 * c.bump(p, 0.36, 0.5)); o('body', 'rx', 0.08 * c.bump(p, 0.36, 0.5));
      const flaps = c.bump(p, 0.45, 0.93) * (0.5 - 0.5 * Math.cos(c.TAU * 3 * (ts - 0.7)));
      o('flipL', 'rz', 1.0 * flaps); o('flipR', 'rz', -1.0 * flaps);
      const sh = c.bump(p, 0.6, 0.78);
      o('head', 'ry', 0.3 * Math.sin(c.TAU * 5.5 * ts) * sh); o('head', 'rz', 0.1 * Math.sin(c.TAU * 5.5 * ts - 1.57) * sh);
      o('body', 'rz', 0.05 * Math.sin((c.TAU * 2 * (p - 0.8)) / 0.2) * c.bump(p, 0.8, 1));
      turn(o, FACE * 0.8 * c.bump(p, 0.05, 0.95), 0);
      o('ctl', 'look', c.env(p, 0.03, 0.08)); o('aux', 'px', 1);
    } },
    talk: { dur: 3, fn(p, o, c) { /* attentive: both eyes on the person, small nods off the beat, one look with one eye */
      const ts = p * 3, e = c.env(p, 0.1, 0.15);
      turn(o, FACE * e, 0);
      o('neck', 'py', 0.03 * e);
      const nod = Math.sin(c.TAU * 1.2 * ts + 0.8 * Math.sin(c.TAU * 0.37 * ts)) * e;
      o('head', 'rx', 0.09 * nod); o('head', 'rz', 0.04 * Math.sin(c.TAU * 0.5 * ts) * e);
      o('flipL', 'rz', 0.1 * Math.max(0, nod)); o('flipR', 'rz', -0.1 * Math.max(0, nod));
      const sn = c.keys(p, [[0, 0], [0.45, 0], [0.5, 1.1], [0.55, 1], [0.75, 1], [0.82, 0], [1, 0]]);
      turn(o, -0.7 * sn, 0); o('neck', 'pz', 0.03 * c.bump(p, 0.45, 0.6));
      o('ctl', 'look', e); o('aux', 'px', 0.5);
    } },
    lookLeft: { dur: 1.2, fn(p, o, c) { /* a one-eyed look to the left of the page: a snap, a poke, a hold */
      const e = c.keys(p, [[0, 0], [0.14, 1.1], [0.22, 1], [0.7, 1], [0.92, 0], [1, 0]]);
      turn(o, -0.6 * e, 0); o('head', 'rx', 0.14 * e); o('neck', 'pz', 0.03 * c.bump(p, 0.02, 0.4));
      o('body', 'ry', -0.06 * e);
      o('ctl', 'look', e);
    } },
    lookRight: { dur: 1.2, fn(p, o, c) {
      const e = c.keys(p, [[0, 0], [0.14, 1.1], [0.22, 1], [0.7, 1], [0.92, 0], [1, 0]]);
      turn(o, 1.1 * e, 0); o('head', 'rx', 0.14 * e); o('neck', 'pz', 0.03 * c.bump(p, 0.02, 0.4));
      o('body', 'ry', 0.1 * e);
      o('ctl', 'look', e);
    } },
    rest: { dur: 8, fn(p, o, c) { /* dozing: lids half down (white showing), the head drawn in, the weight back on heels and tail, feathers a little loose */
      const e = c.env(p, 0.12, 0.12);
      o('ctl', 'lid', 0.55 * e); o('ctl', 'breath', -0.45 * e);
      o('head', 'py', -0.02 * e); o('head', 'rx', 0.17 * e); o('neck', 'rx', 0.05 * e);
      o('body', 'rx', -0.14 * e); o('aux', 'py', 0.35 * e);
      o('flipL', 'rz', -0.04 * e); o('flipR', 'rz', 0.04 * e);
    } },
    dance: { dur: 2.2, fn(p, o, c) { /* the little ecstatic (research/penguin.md section 5) */
      const ts = p * 2.2;
      const rise = c.keys(p, [[0, 0], [0.2, 1], [0.7, 1], [0.84, -0.05], [0.9, 0], [1, 0]]);
      o('head', 'py', 0.08 * rise); o('neck', 'py', 0.02 * rise);
      o('head', 'rx', -1.25 * rise); o('neck', 'rx', -0.25 * rise);
      o('jaw', 'rx', 0.45 * c.keys(p, [[0, 0], [0.13, 0], [0.2, 1], [0.7, 1], [0.78, 0], [1, 0]]));
      const fl = c.keys(p, [[0, 0], [0.045, 0], [0.24, 1], [0.7, 1], [0.84, 0.25], [0.93, 0.02], [1, 0]]);
      o('flipL', 'rz', 1.25 * fl); o('flipR', 'rz', -1.25 * fl);
      o('body', 'py', 0.03 * c.keys(p, [[0, 0], [0.2, 1], [0.84, 1], [0.93, 0], [0.96, -0.4], [1, 0]]));
      const apart = c.keys(p, [[0, 0], [0.1, 0], [0.22, 1], [0.9, 1], [1, 0]]);
      o('footL', 'px', 0.02 * apart); o('footR', 'px', -0.02 * apart);
      const hvE = ts > 0.45 && ts < 1.55 ? c.env((ts - 0.45) / 1.1, 0.12, 0.12) : 0, ph = c.TAU * 2.7 * (ts - 0.45);
      const heave = hvE * (0.5 - 0.5 * Math.cos(ph));
      o('body', 'sx', 0.04 * heave); o('body', 'sz', 0.035 * heave); o('neck', 'sz', 0.05 * heave);
      o('head', 'rx', -0.1 * heave); o('head', 'py', 0.01 * heave);
      o('flipL', 'ry', 0.5 * (heave - 0.5 * hvE)); o('flipR', 'ry', -0.5 * (heave - 0.5 * hvE));      /* horizontal flippers beat fore and aft about the vertical */
      o('aux', 'rx', 0.4 * hvE); o('aux', 'py', 0.6 * hvE);
      o('body', 'rz', 0.07 * Math.sin(ph + 1.57) * hvE);
      const sh = c.bump(p, 0.84, 0.93);
      o('head', 'ry', 0.38 * Math.sin(c.TAU * 5.5 * (ts - 1.85)) * sh); o('head', 'rz', 0.12 * Math.sin(c.TAU * 5.5 * (ts - 1.85) - 1.57) * sh);
      o('ctl', 'lid', c.bump(p, 0.905, 0.985));
      o('ctl', 'look', c.env(p, 0.05, 0.1)); o('aux', 'px', 1);
    } },
  };
  K.finish(R);
  K.restTurn(R, 'neck', [0, NECK_YAW, 0]);      /* bound straight, rests turned: the neck bends smoothly into the turn */
  K.restTurn(R, 'head', [0, HEAD_YAW, 0]);
  return R;
}

export default {
  id: 'penguin',
  name: 'Adélie penguin',
  latin: 'Pygoscelis adeliae',
  rests: 'floor',
  build: (THREE, kit) => buildPenguin(THREE, kit),
  update: (rig, dt, state) => { if (rig.pg) rig.pg.step(dt, state); rig.kit.update(rig, dt, state); },
  play: (rig, clip, variant) => rig.kit.play(rig, clip, variant),
  rest: (rig) => { if (rig.pg) rig.pg.reset(); rig.kit.rest(rig); },
};
