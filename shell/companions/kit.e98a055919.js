/*
  The Civic Archive companions: the realism kit the seven animals share (John, 2026-10-03: "hyper-realistic 3D fully
  animated ... popping off the screen").

  One ES module, created once per page by the dock (or the lab) and handed to each companion's build(THREE, kit):

      import { createKit } from "./kit.js";
      const kit = createKit(THREE, { RoomEnvironment, gltf: () => import(".../GLTFLoader.js") }, { tier, base });

  What it holds (every part optional; a companion uses what its species needs):
    sculpting   sd.* signed distance fields, surf() (a field becomes a smooth, painted, groomed mesh), strip(), circle(),
                prim(), hit(); the same tools the first stand-ins were sculpted with, so an existing sculpt still builds
    materials   physical(o) a MeshPhysicalMaterial that reads the sculpts' per-vertex colour and occlusion, with sheen
                (fur and feathers), clearcoat (beaks, claws, wet skin, shells) and optional per-vertex roughness /
                clearcoat / sheen (attribute aMat); tex.canvas / tex.iris / tex.feather / tex.noise for painted maps;
                mat(o) the old self-lit shader, kept so a part can still be drawn the old way
    fur         fur(R, mesh, o): shell-texture fur or feathers over any mesh (skinned or rigid): strand density, length
                (uniform or per vertex, aFur), comb direction (aComb), clumping, gravity droop, root darkening, tips that
                thin; the number of shells follows the quality tier and can be changed live (R.shells(n))
    rig         rig(spec), joint(), local(), adopt(), put(), skin() (auto-weights by distance to bones, then smoothed, on
                a THREE.SkinnedMesh), eye() (a wet eye: iris texture, additive cornea, a glint that stays toward the
                light, lids that blink), limit() (joint limits), spring() (secondary motion that swings with the body's
                own acceleration and follows through), finish(), update(), play(), rest()
    clips       the same clip model as before: fn(p, o, c) adds to the rest pose over p 0..1; c carries helpers (env,
                bump, ramp, hop, wave, keys, and now walk() for planted feet and ik2() for a bending leg)
    models      loadModel(url) (glTF, GLB or OBJ), fit(), dress(), bonesOf(), anim(): a downloaded model on the rig
    stage       stage(renderer, o): the presentation that pops the animal off the page: a close perspective camera framed
                so the animal fills its dock box while the canvas around it is wider and taller; key, fill and rim lights;
                an environment map (RoomEnvironment through PMREM); a soft contact shadow; pointer parallax; filmic tone
                mapping; shadows from the key light on the full tier
    tiers       tier 0 (lean), 1 (mid phone), 2 (full): caps() says how many shells, what pixel ratio, whether the key light
                casts shadows and whether there is an environment map; setTier(n) applies a change live

  Units: a rig's root is one unit to the animal's body height, facing +z toward the reader, feet at y = 0.
  Colours: black, white, greys, browns, buff; a penguin's pink feet; never red or blue (the site's party colours).
  Nothing here fetches anything unless a companion asks for a model under kit.base.
*/

export function createKit(THREE, loaders = {}, opts = {}) {
  const PI = Math.PI, TAU = 2 * Math.PI;
  const clamp = (x, a, b) => (x < a ? a : x > b ? b : x);
  const lerp = (a, b, t) => a + (b - a) * t;
  const sst = (a, b, x) => {
    if (a === b) return x < a ? 0 : 1;
    const t = clamp((x - a) / (b - a), 0, 1);
    return t * t * (3 - 2 * t);
  };

  /* ---------- quality tiers ---------- */
  const CAPS = [
    { shells: 0, dpr: 1, shadow: 0, env: false, fps: 24, aa: false, eyeSegs: 14 },
    { shells: 6, dpr: 1.5, shadow: 0, env: true, fps: 30, aa: true, eyeSegs: 18 },
    { shells: 14, dpr: 2, shadow: 512, env: true, fps: 30, aa: true, eyeSegs: 24 },
  ];
  let tier = clamp(opts.tier == null ? 2 : opts.tier | 0, 0, 2);
  const tierFns = new Set();
  const caps = (t) => CAPS[clamp(t == null ? tier : t | 0, 0, 2)];
  function setTier(t) {
    t = clamp(t | 0, 0, 2);
    if (t === tier) return tier;
    tier = t;
    for (const f of tierFns) { try { f(tier); } catch (e) {} }
    return tier;
  }

  /* seeded random numbers, so a check can replay a clip exactly */
  function random(seed) {
    let s = seed >>> 0;
    return () => {
      s = (s + 0x6d2b79f5) >>> 0;
      let t = s;
      t = Math.imul(t ^ (t >>> 15), t | 1);
      t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  }

  /* value noise, for mottling, fur and feather texture */
  function h3(i, j, k) {
    let h = Math.imul(i, 0x8da6b343) ^ Math.imul(j, 0xd8163841) ^ Math.imul(k, 0xcb1ab31f);
    h = Math.imul(h ^ (h >>> 13), 0x5bd1e995);
    h ^= h >>> 15;
    return (h >>> 0) / 4294967296;
  }
  function noise(x, y, z) {
    const i = Math.floor(x), j = Math.floor(y), k = Math.floor(z);
    const u = x - i, v = y - j, w = z - k;
    const a = u * u * (3 - 2 * u), b = v * v * (3 - 2 * v), c = w * w * (3 - 2 * w);
    const n000 = h3(i, j, k), n100 = h3(i + 1, j, k), n010 = h3(i, j + 1, k), n110 = h3(i + 1, j + 1, k);
    const n001 = h3(i, j, k + 1), n101 = h3(i + 1, j, k + 1), n011 = h3(i, j + 1, k + 1), n111 = h3(i + 1, j + 1, k + 1);
    return lerp(lerp(lerp(n000, n100, a), lerp(n010, n110, a), b), lerp(lerp(n001, n101, a), lerp(n011, n111, a), b), c);
  }
  function fbm(x, y, z, oct = 3) {
    let s = 0, amp = 0.5, f = 1, n = 0;
    for (let o = 0; o < oct; o++) { s += amp * noise(x * f, y * f, z * f); n += amp; amp *= 0.5; f *= 2.07; }
    return s / n;
  }

  /* colours are written as sRGB hex and stored linear */
  const rgb = (h) => [((h >> 16) & 255) / 255, ((h >> 8) & 255) / 255, (h & 255) / 255];
  const mixc = (a, b, t) => [lerp(a[0], b[0], t), lerp(a[1], b[1], t), lerp(a[2], b[2], t)];
  const lin = (c) => (c <= 0.04045 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4));
  const hex = (c) => '#' + c.map((v) => Math.round(clamp(v, 0, 1) * 255).toString(16).padStart(2, '0')).join('');

  /* ---- signed distance fields; each carries a bounding sphere (f.b) so distant parts are skipped ---- */
  function rot3(r) {
    const e = new THREE.Matrix4().makeRotationFromEuler(new THREE.Euler(r[0] || 0, r[1] || 0, r[2] || 0)).elements;
    return [e[0], e[1], e[2], e[4], e[5], e[6], e[8], e[9], e[10]];
  }
  function smin(a, b, k) {
    if (k <= 0) return a < b ? a : b;
    const h = Math.max(k - Math.abs(a - b), 0) / k;
    return (a < b ? a : b) - h * h * k * 0.25;
  }
  const smax = (a, b, k) => -smin(-a, -b, k);
  const unit = (v) => { const l = Math.hypot(v[0], v[1], v[2]) || 1; return [v[0] / l, v[1] / l, v[2] / l]; };
  const cross = (a, b) => [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]];
  const dot = (a, b) => a[0] * b[0] + a[1] * b[1] + a[2] * b[2];
  const bound = (f, b) => { f.b = b; return f; };
  function around(fs, k) {
    const bs = fs.map((f) => f.b);
    if (bs.some((b) => !b)) return null;
    const lo = [Infinity, Infinity, Infinity], hi = [-Infinity, -Infinity, -Infinity];
    for (const b of bs) for (let i = 0; i < 3; i++) { lo[i] = Math.min(lo[i], b[i] - b[3]); hi[i] = Math.max(hi[i], b[i] + b[3]); }
    const c = [(lo[0] + hi[0]) / 2, (lo[1] + hi[1]) / 2, (lo[2] + hi[2]) / 2];
    let r = 0;
    for (const b of bs) r = Math.max(r, Math.hypot(b[0] - c[0], b[1] - c[1], b[2] - c[2]) + b[3]);
    return [c[0], c[1], c[2], r + (k || 0)];
  }
  function far(b, x, y, z, lim) {
    if (!b) return false;
    const t = lim / 0.6 + b[3];
    if (t <= 0) return true;
    const dx = x - b[0], dy = y - b[1], dz = z - b[2];
    return dx * dx + dy * dy + dz * dz > t * t;
  }
  const sd = {
    ball(c, r) {
      const cx = c[0], cy = c[1], cz = c[2];
      return bound((x, y, z) => { const dx = x - cx, dy = y - cy, dz = z - cz; return Math.sqrt(dx * dx + dy * dy + dz * dz) - r; }, [cx, cy, cz, r]);
    },
    egg(c, r, rot) {
      const cx = c[0], cy = c[1], cz = c[2], m = rot ? rot3(rot) : null, mn = Math.min(r[0], r[1], r[2]);
      const a2 = 1 / (r[0] * r[0]), b2 = 1 / (r[1] * r[1]), d2 = 1 / (r[2] * r[2]);
      return bound((x, y, z) => {
        let px = x - cx, py = y - cy, pz = z - cz;
        if (m) {
          const qx = m[0] * px + m[1] * py + m[2] * pz, qy = m[3] * px + m[4] * py + m[5] * pz, qz = m[6] * px + m[7] * py + m[8] * pz;
          px = qx; py = qy; pz = qz;
        }
        const k0 = Math.sqrt(px * px * a2 + py * py * b2 + pz * pz * d2);
        const k1 = Math.sqrt(px * px * a2 * a2 + py * py * b2 * b2 + pz * pz * d2 * d2);
        return k1 < 1e-9 ? -mn : (k0 * (k0 - 1)) / k1;
      }, [cx, cy, cz, Math.max(r[0], r[1], r[2])]);
    },
    limb(A, B, r1, r2) {
      const ax = A[0], ay = A[1], az = A[2], bx = B[0] - ax, by = B[1] - ay, bz = B[2] - az;
      const l2 = bx * bx + by * by + bz * bz, rr = r1 - r2, a2 = l2 - rr * rr, il2 = 1 / l2, sg = Math.sign(rr);
      return bound((x, y, z) => {
        const px = x - ax, py = y - ay, pz = z - az;
        const yy = px * bx + py * by + pz * bz, zz = yy - l2;
        const qx = px * l2 - bx * yy, qy = py * l2 - by * yy, qz = pz * l2 - bz * yy;
        const x2 = qx * qx + qy * qy + qz * qz, y2 = yy * yy * l2, z2 = zz * zz * l2;
        const k = sg * rr * rr * x2;
        if (Math.sign(zz) * a2 * z2 > k) return Math.sqrt(x2 + z2) * il2 - r2;
        if (Math.sign(yy) * a2 * y2 < k) return Math.sqrt(x2 + y2) * il2 - r1;
        return (Math.sqrt(x2 * a2 * il2) + yy * rr) * il2 - r1;
      }, [ax + bx / 2, ay + by / 2, az + bz / 2, Math.sqrt(l2) / 2 + Math.max(r1, r2)]);
    },
    chain(pts, rads, k) {
      const fs = [];
      for (let i = 0; i < pts.length - 1; i++) fs.push(sd.limb(pts[i], pts[i + 1], rads[i], rads[i + 1]));
      return sd.add(k || 0, ...fs);
    },
    xf(f, c, rot, s) {
      const m = rot ? rot3(rot) : null, cx = c[0], cy = c[1], cz = c[2];
      const sx = s ? s[0] : 1, sy = s ? s[1] : 1, sz = s ? s[2] : 1, k = Math.min(sx, sy, sz);
      let b = null;
      if (f.b) {
        const lx = f.b[0] * sx, ly = f.b[1] * sy, lz = f.b[2] * sz, M = m || [1, 0, 0, 0, 1, 0, 0, 0, 1];
        b = [cx + M[0] * lx + M[3] * ly + M[6] * lz, cy + M[1] * lx + M[4] * ly + M[7] * lz, cz + M[2] * lx + M[5] * ly + M[8] * lz, f.b[3] * Math.max(sx, sy, sz)];
      }
      return bound((x, y, z) => {
        let px = x - cx, py = y - cy, pz = z - cz;
        if (m) {
          const qx = m[0] * px + m[1] * py + m[2] * pz, qy = m[3] * px + m[4] * py + m[5] * pz, qz = m[6] * px + m[7] * py + m[8] * pz;
          px = qx; py = qy; pz = qz;
        }
        return f(px / sx, py / sy, pz / sz) * k;
      }, b);
    },
    add(k, ...fs) {
      const n = fs.length, bs = fs.map((f) => f.b || null);
      return bound((x, y, z) => {
        let d = fs[0](x, y, z);
        for (let i = 1; i < n; i++) if (!far(bs[i], x, y, z, d + k)) d = smin(d, fs[i](x, y, z), k);
        return d;
      }, around(fs, k));
    },
    min(...fs) {
      const n = fs.length, bs = fs.map((f) => f.b || null);
      return bound((x, y, z) => {
        let d = fs[0](x, y, z);
        for (let i = 1; i < n; i++) if (!far(bs[i], x, y, z, d)) { const e = fs[i](x, y, z); if (e < d) d = e; }
        return d;
      }, around(fs, 0));
    },
    sub(f, g, k) { return bound((x, y, z) => smax(f(x, y, z), -g(x, y, z), k || 0), f.b); },
    and(f, g, k) { return bound((x, y, z) => smax(f(x, y, z), g(x, y, z), k || 0), f.b); },
    cut(f, P, N, k) {
      const n = unit(N), px = P[0], py = P[1], pz = P[2];
      return bound((x, y, z) => smax(f(x, y, z), (x - px) * n[0] + (y - py) * n[1] + (z - pz) * n[2], k || 0), f.b);
    },
    erode(f, P, N, amt, band) {
      const n = unit(N), px = P[0], py = P[1], pz = P[2];
      return bound((x, y, z) => f(x, y, z) + amt * sst(0, band, (x - px) * n[0] + (y - py) * n[1] + (z - pz) * n[2]), f.b);
    },
    /* a gentle wave of the surface (for scales, ribs, the shell's growth lines) */
    ripple(f, amp, freq, axis) {
      const a = unit(axis || [0, 1, 0]);
      return bound((x, y, z) => f(x, y, z) + amp * Math.sin(freq * (x * a[0] + y * a[1] + z * a[2])), f.b);
    },
    frame(c, rot) {
      const m = rot ? rot3(rot) : [1, 0, 0, 0, 1, 0, 0, 0, 1], cx = c[0], cy = c[1], cz = c[2];
      return {
        loc(x, y, z) {
          const px = x - cx, py = y - cy, pz = z - cz;
          return [m[0] * px + m[1] * py + m[2] * pz, m[3] * px + m[4] * py + m[5] * pz, m[6] * px + m[7] * py + m[8] * pz];
        },
        place(f, s) { return sd.xf(f, c, rot, s); },
      };
    },
  };

  function probe(f, x, y, z, h, out) {
    const a = f(x + h, y - h, z - h), b = f(x - h, y - h, z + h), c = f(x - h, y + h, z - h), e = f(x + h, y + h, z + h);
    out[0] = (a + b + c + e) * 0.25; out[1] = a - b - c + e; out[2] = -a - b + c + e; out[3] = -a + b - c + e;
    return out;
  }
  function settle(f, x, y, z, h, steps, maxStep, out) {
    const q = [0, 0, 0, 0];
    for (let it = 0; it < steps; it++) {
      probe(f, x, y, z, h, q);
      const g2 = q[1] * q[1] + q[2] * q[2] + q[3] * q[3];
      if (g2 < 1e-16) break;
      let s = (q[0] * 4 * h) / g2;
      const len = Math.abs(s) * Math.sqrt(g2);
      if (len > maxStep) s *= maxStep / len;
      x -= s * q[1]; y -= s * q[2]; z -= s * q[3];
    }
    const gl = Math.sqrt(q[1] * q[1] + q[2] * q[2] + q[3] * q[3]) || 1;
    out[0] = x; out[1] = y; out[2] = z; out[3] = q[1] / gl; out[4] = q[2] / gl; out[5] = q[3] / gl;
    return out;
  }
  function occlusion(aoF, x, y, z, ux, uy, uz, st, ak) {
    let occ = 0, w = 1, tot = 0;
    for (let s = 1; s <= 3; s++) {
      const d = st * s;
      occ += w * Math.max(0, d - aoF(x + ux * d, y + uy * d, z + uz * d)); tot += w * d; w *= 0.65;
    }
    return clamp(1 - (1.6 * ak * occ) / tot, 0.2, 1);
  }
  function geometry(P, N, col, ao, idx, extra) {
    const g = new THREE.BufferGeometry();
    g.setAttribute('position', new THREE.BufferAttribute(P, 3));
    g.setAttribute('normal', new THREE.BufferAttribute(N, 3));
    g.setAttribute('color', new THREE.BufferAttribute(col, 3));
    g.setAttribute('ao', new THREE.BufferAttribute(ao, 1));
    if (extra) for (const k in extra) g.setAttribute(k, new THREE.BufferAttribute(extra[k].array, extra[k].size));
    g.setIndex(idx);
    return g;
  }
  /* groom values per vertex: [len, dens, combX, combY, combZ] (the comb is laid flat on the surface) and, when a sixth
     to eighth value is given, [rough, clearcoat, sheen] multipliers for the material (attribute aMat) */
  function groomAt(groom, matAt, n, x, y, z, nx, ny, nz, fur, comb, matA) {
    if (groom) {
      const g = groom(x, y, z, nx, ny, nz) || [1, 1, 0, 0, 0];
      fur[4 * n] = g[0] == null ? 1 : g[0]; fur[4 * n + 1] = g[1] == null ? 1 : g[1]; fur[4 * n + 2] = g[5] == null ? 0 : g[5]; fur[4 * n + 3] = 0;
      let cx = g[2] || 0, cy = g[3] || 0, cz = g[4] || 0;
      const d = cx * nx + cy * ny + cz * nz;
      cx -= d * nx; cy -= d * ny; cz -= d * nz;
      comb[3 * n] = cx; comb[3 * n + 1] = cy; comb[3 * n + 2] = cz;
    }
    if (matAt) {
      const m = matAt(x, y, z, nx, ny, nz) || [1, 1, 1];
      matA[3 * n] = m[0] == null ? 1 : m[0]; matA[3 * n + 1] = m[1] == null ? 1 : m[1]; matA[3 * n + 2] = m[2] == null ? 1 : m[2];
    }
  }

  /* ---- surface nets: a field becomes a smooth, coloured, shaded, groomed mesh ---- */
  const stats = [];
  const CX = [0, 1, 0, 1, 0, 1, 0, 1], CY = [0, 0, 1, 1, 0, 0, 1, 1], CZ = [0, 0, 0, 0, 1, 1, 1, 1];
  const EA = [0, 2, 4, 6, 0, 1, 4, 5, 0, 1, 2, 3], EB = [1, 3, 5, 7, 2, 3, 6, 7, 4, 5, 6, 7];
  const ROOT = [0, 1, Math.SQRT2, Math.sqrt(3)];
  let detail = opts.detail || 1.2;
  if (!opts.detail) {
    try {
      const nav = typeof navigator !== 'undefined' ? navigator : {};
      if ((nav.deviceMemory && nav.deviceMemory < 4) || (nav.hardwareConcurrency && nav.hardwareConcurrency <= 4)) detail = 1.6;
    } catch (e) { detail = 1.2; }
  }
  function surf(f, box, cell, paint, o = {}) {
    cell *= detail;
    const T0 = performance.now(), x0 = box[0], y0 = box[1], z0 = box[2];
    const nx = 2 * Math.ceil((box[3] - x0) / cell / 2) + 1, ny = 2 * Math.ceil((box[4] - y0) / cell / 2) + 1, nz = 2 * Math.ceil((box[5] - z0) / cell / 2) + 1;
    const sxy = nx * ny, F = new Float32Array(sxy * nz);
    for (let k = 0; k < nz; k += 2) for (let j = 0; j < ny; j += 2) for (let i = 0; i < nx; i += 2) F[i + nx * j + sxy * k] = f(x0 + i * cell, y0 + j * cell, z0 + k * cell);
    for (let k = 0; k < nz; k++) for (let j = 0; j < ny; j++) for (let i = 0; i < nx; i++) {
      const odd = (i & 1) + (j & 1) + (k & 1);
      if (!odd) continue;
      const vc = F[i - (i & 1) + nx * (j - (j & 1)) + sxy * (k - (k & 1))], dist = cell * ROOT[odd];
      F[i + nx * j + sxy * k] = Math.abs(vc) > 1.3 * dist ? vc - Math.sign(vc) * 0.5 * dist : f(x0 + i * cell, y0 + j * cell, z0 + k * cell);
    }
    const cx = nx - 1, cy = ny - 1, cxy = cx * cy;
    const C = new Int32Array(cxy * (nz - 1)).fill(-1), pos = [], v = new Float64Array(8);
    for (let k = 0; k < nz - 1; k++) for (let j = 0; j < ny - 1; j++) for (let i = 0; i < nx - 1; i++) {
      const q = i + nx * j + sxy * k;
      v[0] = F[q]; v[1] = F[q + 1]; v[2] = F[q + nx]; v[3] = F[q + nx + 1];
      v[4] = F[q + sxy]; v[5] = F[q + sxy + 1]; v[6] = F[q + sxy + nx]; v[7] = F[q + sxy + nx + 1];
      let m = 0;
      for (let c = 0; c < 8; c++) if (v[c] < 0) m |= 1 << c;
      if (m === 0 || m === 255) continue;
      let ax = 0, ay = 0, az = 0, n = 0;
      for (let e = 0; e < 12; e++) {
        const a = EA[e], b = EB[e], va = v[a], vb = v[b];
        if ((va < 0) === (vb < 0)) continue;
        const t = va / (va - vb);
        ax += CX[a] + t * (CX[b] - CX[a]); ay += CY[a] + t * (CY[b] - CY[a]); az += CZ[a] + t * (CZ[b] - CZ[a]); n++;
      }
      C[i + cx * j + cxy * k] = pos.length / 3;
      pos.push(x0 + (i + ax / n) * cell, y0 + (j + ay / n) * cell, z0 + (k + az / n) * cell);
    }
    const idx = [];
    const vid = (i, j, k) => C[i + cx * j + cxy * k];
    const d2 = (a, b) => {
      const dx = pos[3 * a] - pos[3 * b], dy = pos[3 * a + 1] - pos[3 * b + 1], dz = pos[3 * a + 2] - pos[3 * b + 2];
      return dx * dx + dy * dy + dz * dz;
    };
    const quad = (a, b, c, d, flip) => {
      if (a < 0 || b < 0 || c < 0 || d < 0) return;
      if (flip) { const t = b; b = d; d = t; }
      if (d2(a, c) <= d2(b, d)) idx.push(a, b, c, a, c, d); else idx.push(a, b, d, b, c, d);
    };
    for (let k = 0; k < nz - 1; k++) for (let j = 0; j < ny - 1; j++) for (let i = 0; i < nx - 1; i++) {
      const q = i + nx * j + sxy * k, in0 = F[q] < 0;
      if (j > 0 && k > 0 && in0 !== F[q + 1] < 0) quad(vid(i, j - 1, k - 1), vid(i, j, k - 1), vid(i, j, k), vid(i, j - 1, k), !in0);
      if (i > 0 && k > 0 && in0 !== F[q + nx] < 0) quad(vid(i - 1, j, k - 1), vid(i - 1, j, k), vid(i, j, k), vid(i, j, k - 1), !in0);
      if (i > 0 && j > 0 && in0 !== F[q + sxy] < 0) quad(vid(i - 1, j - 1, k), vid(i, j - 1, k), vid(i, j, k), vid(i - 1, j, k), !in0);
    }
    const nv = pos.length / 3, P = new Float32Array(nv * 3), N = new Float32Array(nv * 3), col = new Float32Array(nv * 3), ao = new Float32Array(nv);
    const fur = o.groom ? new Float32Array(nv * 4) : null, comb = o.groom ? new Float32Array(nv * 3) : null, matA = o.matAt ? new Float32Array(nv * 3) : null;
    const aoF = o.ao || f, st = o.aoStep || 0.026, ak = o.aoK == null ? 1 : o.aoK, s6 = [0, 0, 0, 0, 0, 0];
    for (let n = 0; n < nv; n++) {
      settle(f, pos[3 * n], pos[3 * n + 1], pos[3 * n + 2], cell * 0.3, 1, cell * 0.5, s6);
      P[3 * n] = s6[0]; P[3 * n + 1] = s6[1]; P[3 * n + 2] = s6[2]; N[3 * n] = s6[3]; N[3 * n + 1] = s6[4]; N[3 * n + 2] = s6[5];
      const c = paint(s6[0], s6[1], s6[2], s6[3], s6[4], s6[5]);
      col[3 * n] = lin(c[0]); col[3 * n + 1] = lin(c[1]); col[3 * n + 2] = lin(c[2]);
      ao[n] = occlusion(aoF, s6[0], s6[1], s6[2], s6[3], s6[4], s6[5], st, ak);
      if (fur || matA) groomAt(o.groom, o.matAt, n, s6[0], s6[1], s6[2], s6[3], s6[4], s6[5], fur, comb, matA);
    }
    stats.push({ cell, vertices: nv, ms: Math.round(performance.now() - T0) });
    const extra = {};
    if (fur) { extra.aFur = { array: fur, size: 4 }; extra.aComb = { array: comb, size: 3 }; }
    if (matA) extra.aMat = { array: matA, size: 3 };
    return geometry(P, N, col, ao, idx, extra);
  }

  /* ---- a strip laid on a surface: crisp rings and lines that follow the shape ---- */
  function strip(f, pts, width, paint, o = {}) {
    const n = pts.length, closed = !!o.closed, lift = o.lift == null ? 0.0012 : o.lift, rows = o.rows || 3;
    const P = [], N = [], cols = [], aos = [], idx = [], c6 = [0, 0, 0, 0, 0, 0], s6 = [0, 0, 0, 0, 0, 0], h = o.h || 0.002;
    for (let i = 0; i < n; i++) {
      const p = pts[i], q = pts[closed ? (i + 1) % n : Math.min(n - 1, i + 1)], r = pts[closed ? (i - 1 + n) % n : Math.max(0, i - 1)];
      settle(f, p[0], p[1], p[2], h, 6, 0.02, c6);
      const t = unit([q[0] - r[0], q[1] - r[1], q[2] - r[2]]), side = unit(cross(t, [c6[3], c6[4], c6[5]]));
      const w = typeof width === 'function' ? width(i) : width;
      for (let k = 0; k < rows; k++) {
        const u = (k / (rows - 1) - 0.5) * w;
        settle(f, c6[0] + side[0] * u, c6[1] + side[1] * u, c6[2] + side[2] * u, h, 4, 0.02, s6);
        P.push(s6[0] + s6[3] * lift, s6[1] + s6[4] * lift, s6[2] + s6[5] * lift);
        N.push(s6[3], s6[4], s6[5]);
        const c = typeof paint === 'function' ? paint(i, k) : paint;
        cols.push(lin(c[0]), lin(c[1]), lin(c[2]));
        aos.push(o.ao ? occlusion(o.ao, s6[0], s6[1], s6[2], s6[3], s6[4], s6[5], 0.024, 1) : 1);
      }
    }
    const segs = closed ? n : n - 1;
    for (let i = 0; i < segs; i++) {
      const a = i * rows, b = ((i + 1) % n) * rows;
      for (let k = 0; k < rows - 1; k++) idx.push(a + k, a + k + 1, b + k + 1, a + k, b + k + 1, b + k);
    }
    const g = geometry(new Float32Array(P), new Float32Array(N), new Float32Array(cols), new Float32Array(aos), idx);
    if (o.flip) { const ia = g.index.array; for (let i = 0; i < ia.length; i += 3) { const t = ia[i + 1]; ia[i + 1] = ia[i + 2]; ia[i + 2] = t; } }
    return g;
  }
  function circle(c, d, radius, n, out = 0) {
    const a = unit(d), up = Math.abs(a[1]) < 0.9 ? [0, 1, 0] : [1, 0, 0];
    const u = unit(cross(up, a)), v = cross(a, u), pts = [];
    for (let i = 0; i < n; i++) {
      const t = (i / n) * TAU, cs = Math.cos(t) * radius, sn = Math.sin(t) * radius;
      pts.push([c[0] + u[0] * cs + v[0] * sn + a[0] * out, c[1] + u[1] * cs + v[1] * sn + a[1] * out, c[2] + u[2] * cs + v[2] * sn + a[2] * out]);
    }
    return pts;
  }
  /* a ready-made three.js shape, given the same attributes as a sculpted one (its uv is kept when o.keepUv) */
  function prim(geo, paint, aoV = 1, o = {}) {
    if (geo.attributes.uv && !o.keepUv) geo.deleteAttribute('uv');
    const p = geo.attributes.position, n = geo.attributes.normal, cnt = p.count;
    const col = new Float32Array(cnt * 3), a = new Float32Array(cnt).fill(aoV);
    for (let i = 0; i < cnt; i++) {
      const c = typeof paint === 'function' ? paint(p.getX(i), p.getY(i), p.getZ(i), n.getX(i), n.getY(i), n.getZ(i)) : paint;
      col[3 * i] = lin(c[0]); col[3 * i + 1] = lin(c[1]); col[3 * i + 2] = lin(c[2]);
    }
    geo.setAttribute('color', new THREE.BufferAttribute(col, 3));
    geo.setAttribute('ao', new THREE.BufferAttribute(a, 1));
    if (o.groom || o.matAt) {
      const fur = o.groom ? new Float32Array(cnt * 4) : null, comb = o.groom ? new Float32Array(cnt * 3) : null, matA = o.matAt ? new Float32Array(cnt * 3) : null;
      for (let i = 0; i < cnt; i++) groomAt(o.groom, o.matAt, i, p.getX(i), p.getY(i), p.getZ(i), n.getX(i), n.getY(i), n.getZ(i), fur, comb, matA);
      if (fur) { geo.setAttribute('aFur', new THREE.BufferAttribute(fur, 4)); geo.setAttribute('aComb', new THREE.BufferAttribute(comb, 3)); }
      if (matA) geo.setAttribute('aMat', new THREE.BufferAttribute(matA, 3));
    }
    return geo;
  }
  /* where a ray from a point first meets a surface */
  function hit(f, from, dir) {
    const d = unit(dir), inside = f(from[0], from[1], from[2]) < 0;
    let t = 0;
    for (let i = 0; i < 96; i++) {
      const s = f(from[0] + d[0] * t, from[1] + d[1] * t, from[2] + d[2] * t);
      if (Math.abs(s) < 1e-6) break;
      t += (inside ? -s : s) * 0.8;
    }
    return [from[0] + d[0] * t, from[1] + d[1] * t, from[2] + d[2] * t];
  }

  /* ---------- painted maps, drawn on a canvas so nothing is fetched ---------- */
  const tex = {
    canvas(w, h, draw, o = {}) {
      const c = document.createElement('canvas'); c.width = w; c.height = h;
      draw(c.getContext('2d'), w, h);
      const t = new THREE.CanvasTexture(c);
      t.colorSpace = o.linear ? THREE.NoColorSpace : THREE.SRGBColorSpace;
      t.wrapS = t.wrapT = o.repeat ? THREE.RepeatWrapping : THREE.ClampToEdgeWrapping;
      t.anisotropy = 2;
      return t;
    },
    /* grey noise, tileable enough for roughness and bump */
    noise(size = 128, scale = 6, oct = 3, o = {}) {
      return tex.canvas(size, size, (g) => {
        const img = g.createImageData(size, size), d = img.data;
        for (let y = 0; y < size; y++) for (let x = 0; x < size; x++) {
          const v = fbm((x / size) * scale, (y / size) * scale, 0.37, oct), i = 4 * (x + y * size);
          const k = Math.round(clamp(lerp(o.lo == null ? 0.35 : o.lo, o.hi == null ? 0.85 : o.hi, v), 0, 1) * 255);
          d[i] = d[i + 1] = d[i + 2] = k; d[i + 3] = 255;
        }
        g.putImageData(img, 0, 0);
      }, { linear: true, repeat: true });
    },
    /* an eye's map on a sphere turned so its +y pole looks along +z: the iris sits at the top of the image */
    iris(o = {}) {
      const W = 128, H = 64, irisA = o.irisAngle == null ? 0.62 : o.irisAngle, pupil = o.pupil == null ? 0.42 : o.pupil;
      const ic = o.iris == null ? [0.20, 0.12, 0.07] : rgb(o.iris), ic2 = o.iris2 == null ? mixc(ic, [0.55, 0.38, 0.2], 0.5) : rgb(o.iris2);
      const sc = o.sclera == null ? [0.93, 0.9, 0.86] : rgb(o.sclera), limb = o.limbal == null ? [0.05, 0.03, 0.02] : rgb(o.limbal);
      const pc = o.pupilColor == null ? [0.01, 0.008, 0.006] : rgb(o.pupilColor);
      return tex.canvas(W, H, (g) => {
        const img = g.createImageData(W, H), d = img.data;
        for (let y = 0; y < H; y++) {
          const th = ((y + 0.5) / H) * PI, r = th / irisA;
          for (let x = 0; x < W; x++) {
            const i = 4 * (x + y * W), u = x / W;
            let c;
            if (r >= 1.04) c = mixc(sc, [sc[0] * 0.85, sc[1] * 0.83, sc[2] * 0.8], sst(1.04, 1.6, r) * 0.5);
            else if (r >= 0.96) c = mixc(limb, sc, sst(0.96, 1.04, r));
            else {
              const fib = 0.5 + 0.5 * Math.sin(u * TAU * 36 + r * 9) * (0.6 + 0.4 * Math.sin(u * TAU * 7));
              const base = mixc(ic, ic2, 0.55 * fib * sst(0.3, 0.95, r)), dark = mixc(base, limb, sst(0.7, 1, r) * 0.7);
              const inPupil = sst(pupil + 0.04, pupil - 0.02, r);
              c = mixc(dark, pc, inPupil);
            }
            d[i] = Math.round(c[0] * 255); d[i + 1] = Math.round(c[1] * 255); d[i + 2] = Math.round(c[2] * 255); d[i + 3] = 255;
          }
        }
        g.putImageData(img, 0, 0);
      });
    },
    /* one feather: a shaft, barbs that thin to the edge, alpha outside; use with a PlaneGeometry card */
    feather(o = {}) {
      const W = o.w || 64, H = o.h || 128, col = o.color == null ? [0.2, 0.2, 0.21] : rgb(o.color), col2 = o.edge == null ? mixc(col, [1, 1, 1], 0.35) : rgb(o.edge);
      return tex.canvas(W, H, (g) => {
        const img = g.createImageData(W, H), d = img.data;
        for (let y = 0; y < H; y++) for (let x = 0; x < W; x++) {
          const i = 4 * (x + y * W), v = y / H, u = (x / W) * 2 - 1;
          const half = 0.08 + 0.92 * Math.sin(Math.min(1, v * 1.08) * PI) ** 0.6;
          const barb = 0.65 + 0.35 * Math.sin((u * 18 + v * 60) * TAU / 6 + fbm(u * 3, v * 9, 1, 2) * 3);
          const inside = Math.abs(u) < half * (0.92 + 0.08 * fbm(u * 8, v * 30, 2, 2));
          const shaft = Math.abs(u) < 0.045 * (1 - v * 0.6);
          const c = shaft ? mixc(col, [0.1, 0.1, 0.1], 0.4) : mixc(col, col2, Math.abs(u) / half * 0.8 * barb);
          d[i] = Math.round(c[0] * 255); d[i + 1] = Math.round(c[1] * 255); d[i + 2] = Math.round(c[2] * 255);
          d[i + 3] = inside || shaft ? Math.round(255 * (shaft ? 1 : clamp((half - Math.abs(u)) / half * 6, 0.35, 1) * barb)) : 0;
        }
        g.putImageData(img, 0, 0);
      });
    },
  };

  /* ---------- the physical material, extended for the sculpts' attributes and for fur shells ---------- */
  const SC = THREE.ShaderChunk;
  const FUR_FRAG = `
uniform float uShell; uniform float uFurDens; uniform float uRootDark; uniform float uFurThin; uniform float uClump; uniform float uAO; uniform float uFurMin;
varying vec3 vFurP; varying vec3 vFurN; varying float vFurH;
#ifdef TCA_VAO
varying float vAO;
#endif
#ifdef TCA_VMAT
varying vec3 vMat;
#endif
float tcaHash(vec2 p){ vec3 q = fract(vec3(p.xyx) * vec3(0.1031, 0.1030, 0.0973)); q += dot(q, q.yzx + 33.33); return fract((q.x + q.y) * q.z); }
`;
  const FUR_VERT = `
uniform float uShell; uniform float uFurLen; uniform float uComb; uniform float uDroop; uniform vec3 uGravity;
varying vec3 vFurP; varying vec3 vFurN; varying float vFurH;
#ifdef TCA_FURATTR
attribute vec4 aFur; attribute vec3 aComb;
#endif
#ifdef TCA_VAO
attribute float ao; varying float vAO;
#endif
#ifdef TCA_VMAT
attribute vec3 aMat; varying vec3 vMat;
#endif
`;
  const FUR_BEGIN = `
vec3 transformed = vec3( position );
vFurP = position; vFurN = objectNormal; vFurH = uShell;
#ifdef TCA_VAO
vAO = ao;
#endif
#ifdef TCA_VMAT
vMat = aMat;
#endif
#ifdef TCA_FUR
{
  #ifdef TCA_FURATTR
  float fl = uFurLen * aFur.x; vec3 cmb = aComb;
  #else
  float fl = uFurLen; vec3 cmb = vec3(0.0);
  #endif
  float h = uShell;
  transformed += objectNormal * (fl * h) + cmb * (fl * h * h * uComb) + uGravity * (fl * h * h * uDroop);
}
#endif
#ifdef USE_ALPHAHASH
vPosition = vec3( position );
#endif
`;
  const FUR_DISCARD = `
#ifdef TCA_FUR
{
  vec3 an = abs(vFurN);
  vec2 q = (an.x > an.y && an.x > an.z) ? vFurP.yz : ((an.y > an.z) ? vFurP.xz : vFurP.xy);
  #ifdef TCA_FURATTR
  float dens = uFurDens * max(0.05, vFurDens);
  #else
  float dens = uFurDens;
  #endif
  q *= dens;
  vec2 cq = (floor(q * 0.31) + 0.5) / 0.31;
  q = mix(q, cq, uClump * 0.22);
  vec2 cell = floor(q), f = q - cell;
  float len = mix(uFurMin, 1.0, tcaHash(cell));
  vec2 c = vec2(tcaHash(cell + 1.3), tcaHash(cell + 2.7)) * 0.56 + 0.22;
  float d = length(f - c);
  float thick = 0.46 * (1.0 - vFurH * uFurThin);
  if (d > thick || vFurH > len) discard;
}
#endif
`;
  const FUR_COLOR = `
#include <color_fragment>
#ifdef TCA_FURROOT
diffuseColor.rgb *= mix(uRootDark, 1.0, vFurH);
#endif
`;
  const AO_FRAG = `
#ifdef TCA_VAO
{
  float tcaAO = mix(1.0, vAO, uAO);
  reflectedLight.indirectDiffuse *= tcaAO;
  reflectedLight.directDiffuse *= mix(1.0, tcaAO, 0.55);
  reflectedLight.directSpecular *= mix(1.0, tcaAO, 0.55);
  #if defined( USE_CLEARCOAT )
  clearcoatSpecularIndirect *= tcaAO;
  #endif
  #if defined( USE_SHEEN )
  sheenSpecularIndirect *= tcaAO;
  #endif
  #if defined( USE_ENVMAP ) && defined( STANDARD )
  float tcaNV = saturate( dot( geometryNormal, geometryViewDir ) );
  reflectedLight.indirectSpecular *= computeSpecularOcclusion( tcaNV, tcaAO, material.roughness );
  #endif
}
#endif
#include <aomap_fragment>
`;
  const VARY_DENS = `
#ifdef TCA_FURATTR
varying float vFurDens;
#endif
`;
  let physN = 0;
  function physical(o = {}) {
    const m = new THREE.MeshPhysicalMaterial({
      color: o.color == null ? 0xffffff : o.color, vertexColors: o.vertexColors !== false,
      roughness: o.rough == null ? 0.62 : o.rough, metalness: o.metal || 0,
      clearcoat: o.clearcoat || 0, clearcoatRoughness: o.ccRough == null ? 0.22 : o.ccRough,
      sheen: o.sheen || 0, sheenRoughness: o.sheenRough == null ? 0.55 : o.sheenRough, sheenColor: new THREE.Color(o.sheenColor == null ? 0xffffff : o.sheenColor),
      specularIntensity: o.spec == null ? 0.55 : o.spec, envMapIntensity: o.env == null ? 1 : o.env,
      side: o.side || THREE.FrontSide, map: o.map || null, normalMap: o.normalMap || null, roughnessMap: o.roughMap || null,
      transparent: !!o.transparent, opacity: o.opacity == null ? 1 : o.opacity, depthWrite: o.depthWrite !== false,
      emissive: new THREE.Color(o.emissive == null ? 0x000000 : o.emissive), emissiveIntensity: o.emissiveI == null ? 1 : o.emissiveI,
      flatShading: false,
    });
    if (o.blending) m.blending = o.blending;
    if (o.normalScale != null) m.normalScale.set(o.normalScale, o.normalScale);
    if (o.ior != null) m.ior = o.ior;
    m.name = o.name || 'tca-physical-' + (physN++);
    const u = {
      uShell: { value: 0 }, uFurLen: { value: o.furLen || 0.02 }, uFurDens: { value: o.furDens || 60 }, uRootDark: { value: o.rootDark == null ? 0.72 : o.rootDark },
      uFurThin: { value: o.furThin == null ? 0.75 : o.furThin }, uClump: { value: o.clump == null ? 0.4 : o.clump }, uComb: { value: o.comb == null ? 0.6 : o.comb },
      uDroop: { value: o.droop == null ? 0.25 : o.droop }, uGravity: { value: new THREE.Vector3(0, -1, 0) }, uAO: { value: o.ao == null ? 0.9 : o.ao }, uFurMin: { value: o.furMin == null ? 0.3 : o.furMin },
    };
    m.userData.tca = Object.assign({}, o); m.userData.u = u; m.defines = Object.assign({}, m.defines || {});
    m.onBeforeCompile = (shader) => {
      Object.assign(shader.uniforms, u);
      shader.vertexShader = shader.vertexShader
        .replace('#include <common>', '#include <common>\n' + FUR_VERT + VARY_DENS)
        .replace('#include <begin_vertex>', FUR_BEGIN + '\n#ifdef TCA_FURATTR\nvFurDens = aFur.y;\n#endif\n');
      let fs = shader.fragmentShader
        .replace('#include <common>', '#include <common>\n' + FUR_FRAG + VARY_DENS)
        .replace('#include <clipping_planes_fragment>', '#include <clipping_planes_fragment>\n' + FUR_DISCARD)
        .replace('#include <color_fragment>', FUR_COLOR)
        .replace('#include <aomap_fragment>', AO_FRAG)
        .replace('#include <roughnessmap_fragment>', '#include <roughnessmap_fragment>\n#ifdef TCA_VMAT\nroughnessFactor = clamp(roughnessFactor * vMat.x, 0.02, 1.0);\n#endif\n');
      const lp = SC.lights_physical_fragment;
      if (lp && fs.includes('#include <lights_physical_fragment>')) {
        let chunk = lp;
        if (chunk.includes('material.clearcoat = clearcoat;')) chunk = chunk.replace('material.clearcoat = clearcoat;', 'material.clearcoat = clearcoat\n#ifdef TCA_VMAT\n * vMat.y\n#endif\n;');
        if (chunk.includes('material.sheenColor = sheenColor;')) chunk = chunk.replace('material.sheenColor = sheenColor;', 'material.sheenColor = sheenColor\n#ifdef TCA_VMAT\n * vMat.z\n#endif\n;');
        fs = fs.replace('#include <lights_physical_fragment>', chunk);
      }
      shader.fragmentShader = fs;
    };
    m.customProgramCacheKey = () => 'tca-phys-2';
    return m;
  }
  /* the material's defines follow the geometry it is put on (which attributes exist), once: a material shared between
     a groomed part and a plain one keeps the first part's settings, and says so once */
  function tune(m, geo) {
    if (!m || !m.userData || !m.userData.u || !geo) return;
    const want = { TCA_VAO: !!geo.attributes.ao, TCA_FURATTR: !!geo.attributes.aFur, TCA_VMAT: !!geo.attributes.aMat };
    if (m.userData.tuned) {
      for (const k in want) if (want[k] !== (k in m.defines) && !m.userData.warned) { m.userData.warned = true; console.warn('companion kit: material "' + m.name + '" is shared by parts with different attributes (' + k + '); give each its own physical()'); }
      return;
    }
    let changed = false;
    for (const k in want) {
      const has = k in m.defines;
      if (want[k] && !has) { m.defines[k] = ''; changed = true; }
      else if (!want[k] && has) { delete m.defines[k]; changed = true; }
    }
    m.userData.tuned = true;
    if (changed) m.needsUpdate = true;
  }

  /* ---- the old self-lit shader, kept for parts a companion still draws that way ---- */
  const VS = `attribute float ao;
varying vec3 vN; varying vec3 vC; varying float vA; varying vec3 vV;
void main(){
  vec4 mv = modelViewMatrix * vec4(position, 1.0);
  vN = normalize(normalMatrix * normal); vC = color; vA = ao; vV = -mv.xyz;
  gl_Position = projectionMatrix * mv;
}`;
  const FS = `uniform float uWrap; uniform float uRim; uniform float uSpec; uniform float uShin; uniform float uSheen;
varying vec3 vN; varying vec3 vC; varying float vA; varying vec3 vV;
void main(){
  vec3 n = normalize(vN); vec3 v = normalize(vV);
  vec3 L = normalize(vec3(-0.45, 0.78, 0.6)); vec3 F = normalize(vec3(0.75, 0.05, 0.45));
  float k = dot(n, L);
  float dif = max((k + uWrap) / (1.0 + uWrap), 0.0);
  float fil = max(dot(n, F), 0.0);
  float hemi = 0.5 + 0.5 * n.y;
  vec3 amb = mix(vec3(0.30, 0.28, 0.26), vec3(0.58, 0.59, 0.61), hemi);
  vec3 lit = amb + vec3(1.0, 0.965, 0.91) * dif * 0.78 + vec3(0.62, 0.62, 0.64) * fil * 0.2;
  float ao = mix(1.0, vA, 0.92);
  vec3 col = vC * lit * ao;
  float fr = pow(1.0 - clamp(dot(n, v), 0.0, 1.0), 2.6);
  col += (vC * 0.7 + 0.1) * fr * uRim * ao;
  col += vC * uSheen * pow(max(k, 0.0), 0.5) * fr;
  vec3 h = normalize(L + v);
  col += vec3(uSpec * pow(max(dot(n, h), 0.0), uShin)) * mix(1.0, vA, 0.6);
  gl_FragColor = vec4(col, 1.0);
  #include <colorspace_fragment>
}`;
  const mats = new Map();
  function mat(o = {}) {
    const key = [o.wrap, o.rim, o.spec, o.shin, o.sheen].join('|');
    if (mats.has(key)) return mats.get(key);
    const m = new THREE.ShaderMaterial({
      vertexShader: VS, fragmentShader: FS, vertexColors: true,
      uniforms: {
        uWrap: { value: o.wrap == null ? 0.4 : o.wrap }, uRim: { value: o.rim == null ? 0.3 : o.rim },
        uSpec: { value: o.spec == null ? 0.04 : o.spec }, uShin: { value: o.shin == null ? 20 : o.shin },
        uSheen: { value: o.sheen == null ? 0 : o.sheen },
      },
    });
    mats.set(key, m);
    return m;
  }

  /* ---------- fur and feathers: shells over a mesh ---------- */
  function fur(R, mesh, o = {}) {
    const base = mesh.material, bo = Object.assign({}, (base.userData && base.userData.tca) || {}, o);
    const u0 = base.userData && base.userData.u;
    if (u0) {
      if (o.len != null) u0.uFurLen.value = o.len; if (o.dens != null) u0.uFurDens.value = o.dens; if (o.root != null) u0.uRootDark.value = o.root;
      if (o.thin != null) u0.uFurThin.value = o.thin; if (o.clump != null) u0.uClump.value = o.clump; if (o.comb != null) u0.uComb.value = o.comb;
      if (o.droop != null) u0.uDroop.value = o.droop; if (o.min != null) u0.uFurMin.value = o.min;
      if (o.root !== 0) { base.defines.TCA_FURROOT = ''; base.needsUpdate = true; }
    }
    const maxShells = o.max || CAPS[2].shells, shells = [], parent = mesh.parent;
    const geo = mesh.geometry;
    for (let i = 0; i < maxShells; i++) {
      const m = physical(Object.assign({}, bo, {
        furLen: o.len == null ? bo.furLen : o.len, furDens: o.dens == null ? bo.furDens : o.dens, rootDark: o.root == null ? bo.rootDark : o.root,
        furThin: o.thin == null ? bo.furThin : o.thin, clump: o.clump == null ? bo.clump : o.clump, comb: o.comb == null ? bo.comb : o.comb,
        droop: o.droop == null ? bo.droop : o.droop, furMin: o.min == null ? bo.furMin : o.min, name: (base.name || 'fur') + '-shell' + i,
      }));
      m.defines.TCA_FUR = ''; if (o.root !== 0) m.defines.TCA_FURROOT = '';
      m.side = o.side || THREE.FrontSide;
      tune(m, geo);
      const s = mesh.isSkinnedMesh ? new THREE.SkinnedMesh(geo, m) : new THREE.Mesh(geo, m);
      s.name = (mesh.name || 'part') + '-shell' + i; s.frustumCulled = false; s.castShadow = false; s.receiveShadow = !!mesh.receiveShadow;
      s.renderOrder = (mesh.renderOrder || 0) + 1 + i;
      s.matrixAutoUpdate = mesh.matrixAutoUpdate;
      s.position.copy(mesh.position); s.quaternion.copy(mesh.quaternion); s.scale.copy(mesh.scale);
      if (parent) parent.add(s);
      shells.push(s); R.mats.add(m);
    }
    const G = { mesh, shells, count: 0, set(n) {
      n = clamp(n | 0, 0, shells.length); G.count = n;
      for (let i = 0; i < shells.length; i++) { const s = shells[i]; s.visible = i < n; if (i < n) s.material.userData.u.uShell.value = (i + 1) / n; }
    } };
    G.set(o.shells == null ? caps().shells : o.shells);
    R.furs.push(G);
    if (mesh.isSkinnedMesh) {
      const rec = R.skins.find((k) => k.mesh === mesh);
      if (rec) { rec.extra.push(...shells); if (rec.skeleton) for (const s of shells) s.bind(rec.skeleton, mesh.bindMatrix); }
      else if (mesh.skeleton) for (const s of shells) s.bind(mesh.skeleton, mesh.bindMatrix);      // a downloaded model's own skeleton
    }
    return G;
  }

  /* ---------- the rig: joints (bones), rest pose, skinning, eyes, limits, springs ---------- */
  const CH = { px: 0, py: 1, pz: 2, rx: 3, ry: 4, rz: 5, sx: 6, sy: 7, sz: 8 };
  const IDLES = ['idleA', 'idleB', 'lookLeft', 'lookRight', 'notice'];
  const REST_AFTER = 30;
  let seedNext = opts.seed;
  function rig(spec) {
    const root = new THREE.Object3D();
    root.name = 'companion-' + spec.id;
    let seed = spec.seed != null ? spec.seed : seedNext != null ? seedNext : (Math.random() * 4294967296) >>> 0;
    const R = {
      root, kit: K, spec, frame: spec.frame, fov: spec.fov, clips: {}, j: {}, piv: {}, rest0: {}, acc: {}, names: [], lids: [], eyes: [],
      mats: new Set(), geos: [], skins: [], furs: [], limits: {}, springs: [], anims: [], t: 0, cur: null, fading: [], ctl: { lid: 0, look: 0, breath: 0, amp: 0 },
      rnd: random(seed), seed,
      phase: 0, nextBlink: 1.3, blinkT: -1, blinkAgain: false, nextIdle: 3, lastIdle: '', duck: 0, check: false, noSprings: false,
      look: { y: 0, p: 0, vy: 0, vp: 0, ty: 0, tp: 0, sy: 0, sp: 0, hold: 0, until: 0, px: null, py: null },
      tmp: { v: new THREE.Vector3(), v2: new THREE.Vector3(), v3: new THREE.Vector3(), q: new THREE.Quaternion(), m: new THREE.Matrix4(), z: new THREE.Vector3(0, 0, 1) },
    };
    const mover = new THREE.Object3D();
    mover.name = 'mover'; root.add(mover); R.j.mover = mover; R.piv.mover = [0, 0, 0];
    const pose = new THREE.Object3D();
    pose.name = 'pose'; pose.rotation.y = spec.yaw || 0; mover.add(pose); R.j.pose = pose; R.piv.pose = [0, 0, 0];
    R.dispose = () => { for (const g of R.geos) g.dispose(); for (const m of R.mats) { for (const k in m) { const v = m[k]; if (v && v.isTexture) v.dispose(); } m.dispose(); } };
    R.shells = (n) => { for (const G of R.furs) G.set(n == null ? caps().shells : n); };
    return R;
  }
  /* a joint whose pivot is given in the sculpting space; a rest turn (rot) turns everything hung on it. Joints are bones,
     so a skinned mesh can bend over them */
  function joint(R, name, parent, pivot, rot) {
    const par = parent || 'pose', pp = R.piv[par], o = new THREE.Bone();
    o.name = name;
    o.position.set(pivot[0] - pp[0], pivot[1] - pp[1], pivot[2] - pp[2]);
    if (rot) o.rotation.set(rot[0], rot[1], rot[2]);
    R.j[par].add(o); R.j[name] = o; R.piv[name] = pivot.slice();
    return o;
  }
  function local(R, name, parent, pos, rot) {
    const o = new THREE.Bone();
    o.name = name; o.position.set(pos[0], pos[1], pos[2]);
    if (rot) o.rotation.set(rot[0], rot[1], rot[2]);
    R.j[parent].add(o); R.j[name] = o; R.piv[name] = null;
    return o;
  }
  /* an object that already exists (a downloaded model's bone) becomes a joint the clips can drive */
  function adopt(R, name, obj) {
    obj.name = obj.name || name; R.j[name] = obj; R.piv[name] = null;
    return obj;
  }
  /* hang a mesh on a joint; sculpted geometry is moved from the sculpting space to the joint's pivot */
  function put(R, name, geo, material, isLocal) {
    if (!isLocal) { const p = R.piv[name]; geo.translate(-p[0], -p[1], -p[2]); }
    tune(material, geo);
    const m = new THREE.Mesh(geo, material);
    m.name = name + '-mesh'; m.frustumCulled = false; m.castShadow = true; m.receiveShadow = true;
    R.j[name].add(m); R.geos.push(geo); R.mats.add(material);
    return m;
  }
  /* distance from a point to a segment */
  function segDist(px, py, pz, a, b) {
    const abx = b[0] - a[0], aby = b[1] - a[1], abz = b[2] - a[2], l2 = abx * abx + aby * aby + abz * abz;
    let t = l2 > 0 ? ((px - a[0]) * abx + (py - a[1]) * aby + (pz - a[2]) * abz) / l2 : 0;
    t = clamp(t, 0, 1);
    const qx = a[0] + abx * t, qy = a[1] + aby * t, qz = a[2] + abz * t;
    return Math.hypot(px - qx, py - qy, pz - qz);
  }
  /* auto-weights: every vertex is tied to the bones nearest its position (distance to the bone's segment, a Gaussian
     falloff with the bone's own radius; a bone's `only(x, y, z)` region fades it out where it must not reach, as a body
     bone must not reach the eyes), then the weights are smoothed over the mesh's edges so no seam shows at a joint */
  function autoSkin(geo, bones, o = {}) {
    const P = geo.attributes.position, n = P.count, nb = bones.length, W = new Float32Array(n * nb);
    for (let v = 0; v < n; v++) {
      const x = P.getX(v), y = P.getY(v), z = P.getZ(v);
      let sum = 0, best = 0, bestW = -1;
      for (let i = 0; i < nb; i++) {
        const B = bones[i], d = segDist(x, y, z, B.a, B.b), r = B.r || 0.1;
        let w = Math.exp(-(d * d) / (r * r)) * (B.w == null ? 1 : B.w);
        if (B.only) { const k = B.only(x, y, z); w *= k === true ? 1 : k ? +k : 0; }      /* a region: false or 0 keeps the bone out, a fraction fades it */
        W[v * nb + i] = w; sum += w;
        if (w > bestW) { bestW = w; best = i; }
      }
      if (sum < 1e-30) { W[v * nb + best] = 1; } else for (let i = 0; i < nb; i++) W[v * nb + i] /= sum;
    }
    const iters = o.smooth == null ? 3 : o.smooth;
    if (iters > 0 && geo.index) {
      const ia = geo.index.array, adj = new Array(n);
      for (let i = 0; i < n; i++) adj[i] = [];
      for (let i = 0; i < ia.length; i += 3) {
        const a = ia[i], b = ia[i + 1], c = ia[i + 2];
        adj[a].push(b, c); adj[b].push(a, c); adj[c].push(a, b);
      }
      let cur = W, nxt = new Float32Array(n * nb);
      for (let it = 0; it < iters; it++) {
        for (let v = 0; v < n; v++) {
          const nb2 = adj[v], m = nb2.length;
          for (let i = 0; i < nb; i++) {
            let s = 0;
            for (let k = 0; k < m; k++) s += cur[nb2[k] * nb + i];
            nxt[v * nb + i] = m ? 0.5 * cur[v * nb + i] + 0.5 * (s / m) : cur[v * nb + i];
          }
        }
        const t = cur; cur = nxt; nxt = t;
      }
      if (cur !== W) W.set(cur);
    }
    const si = new Uint16Array(n * 4), sw = new Float32Array(n * 4), order = new Array(nb);
    for (let v = 0; v < n; v++) {
      for (let i = 0; i < nb; i++) order[i] = i;
      order.sort((a, b) => W[v * nb + b] - W[v * nb + a]);
      let s = 0;
      for (let k = 0; k < 4; k++) { const i = k < nb ? order[k] : 0; si[v * 4 + k] = i; sw[v * 4 + k] = k < nb ? W[v * nb + i] : 0; s += sw[v * 4 + k]; }
      if (s > 0) for (let k = 0; k < 4; k++) sw[v * 4 + k] /= s; else sw[v * 4] = 1;
    }
    geo.setAttribute('skinIndex', new THREE.BufferAttribute(si, 4));
    geo.setAttribute('skinWeight', new THREE.BufferAttribute(sw, 4));
    return geo;
  }
  /* a sculpted mesh in the sculpting space bends over the rig's bones. bones: [{j: 'head', a: [x,y,z], b: [x,y,z], r}]
     in sculpting space; the mesh hangs under 'pose'. The binding is done in finish(), when the rest pose is final */
  function skin(R, geo, bones, material, o = {}) {
    for (const B of bones) if (!R.j[B.j]) throw new Error('skin: no joint ' + B.j);
    autoSkin(geo, bones, o);
    tune(material, geo);
    const m = new THREE.SkinnedMesh(geo, material);
    m.name = (o.name || 'skin') + '-mesh'; m.frustumCulled = false; m.castShadow = true; m.receiveShadow = true;
    R.j.pose.add(m); R.geos.push(geo); R.mats.add(material);
    R.skins.push({ mesh: m, bones: bones.map((B) => R.j[B.j]), extra: [] });
    return m;
  }
  /* a wet eye looking along dir: a sphere with an iris map (pupil, fibres, a limbal ring), a transparent cornea that only
     adds its reflections, a glint that stays toward the light, an upper lid that blinks and a lower lid that rises a little */
  function eye(R, name, parent, c, dir, r, o = {}) {
    const d = new THREE.Vector3(dir[0], dir[1], dir[2]).normalize();
    const q = new THREE.Quaternion().setFromUnitVectors(new THREE.Vector3(0, 0, 1), d);
    const e = new THREE.Euler().setFromQuaternion(q);
    const pp = R.piv[parent] || [0, 0, 0];
    const j = local(R, name, parent, o.isLocal ? c : [c[0] - pp[0], c[1] - pp[1], c[2] - pp[2]], [e.x, e.y, e.z]);
    const segs = o.segs || caps().eyeSegs;
    const ball = new THREE.SphereGeometry(r, segs, Math.round(segs * 0.7));
    ball.rotateX(PI / 2);
    const irisTex = o.map || tex.iris({ iris: o.iris == null ? 0x2a1a0e : o.iris, iris2: o.iris2, sclera: o.sclera == null ? 0xece6dc : o.sclera, pupil: o.pupil == null ? 0.42 : o.pupil, irisAngle: o.irisAngle == null ? 0.62 : o.irisAngle, limbal: o.limbal });
    const em = physical({ color: 0xffffff, vertexColors: false, rough: 0.3, clearcoat: o.gloss == null ? 0.6 : o.gloss, ccRough: 0.1, spec: 0.7, env: 0.55, map: irisTex, name: name + '-ball' });
    const ballM = new THREE.Mesh(ball, em);
    ballM.name = name + '-mesh'; ballM.frustumCulled = false; ballM.castShadow = false; ballM.receiveShadow = true;
    j.add(ballM); R.geos.push(ball); R.mats.add(em);
    /* the cornea adds only its reflections: black, glossy, additive */
    const cap = new THREE.SphereGeometry(r * 1.035, segs, Math.round(segs * 0.4), 0, TAU, 0, o.corneaAngle || 0.95);
    cap.rotateX(PI / 2);
    const cm = physical({ color: 0x000000, vertexColors: false, rough: 0.05, clearcoat: 0.5, ccRough: 0.06, spec: 0.5, env: o.wet == null ? 0.35 : o.wet, transparent: true, depthWrite: false, blending: THREE.AdditiveBlending, name: name + '-cornea' });
    const capM = new THREE.Mesh(cap, cm);
    capM.name = name + '-cornea'; capM.frustumCulled = false; capM.castShadow = false; capM.receiveShadow = false; capM.renderOrder = 20;
    j.add(capM); R.geos.push(cap); R.mats.add(cm);
    /* the glint: a small bright disc that sits on the cornea toward the light (placed every frame) */
    const gs = (o.glint == null ? 0.3 : o.glint) * r;
    const gg = new THREE.SphereGeometry(gs, 10, 8);
    const gm = new THREE.MeshBasicMaterial({ color: 0xffffff, toneMapped: false, transparent: true, opacity: o.glintA == null ? 0.9 : o.glintA, depthWrite: false });
    const glint = new THREE.Mesh(gg, gm);
    glint.name = name + '-glint'; glint.frustumCulled = false; glint.renderOrder = 21; glint.scale.set(1, 1, 0.35);
    glint.position.set(-r * 0.35, r * 0.45, r * 0.9);
    j.add(glint); R.geos.push(gg); R.mats.add(gm);
    const open = o.open == null ? -0.6 : o.open, shut = o.shut == null ? 1.5 : o.shut;
    const lidJ = local(R, name + 'Lid', name, [0, 0, 0], [open, 0, 0]);
    const lidR = r * (o.lidScale || 1.1), lidCol = o.lid || rgb(0x222222);
    const lg = prim(new THREE.SphereGeometry(lidR, segs, Math.round(segs * 0.45), 0, TAU, 0, PI / 2 + 0.1), lidCol);
    const lidMat = o.lidMaterial || physical(o.lidMat || { rough: 0.6, sheen: 0.3, name: name + '-lid' });
    put(R, lidJ.name, lg, lidMat, true);
    R.lids.push({ n: lidJ.name, ch: 'rx', shut: shut - open });
    if (o.lower !== false) {
      const loJ = local(R, name + 'LidLo', name, [0, 0, 0], [PI - open * 0.4, 0, 0]);
      const lo = prim(new THREE.SphereGeometry(lidR * 0.995, segs, Math.round(segs * 0.3), 0, TAU, 0, 0.75), o.lidLo || lidCol);
      put(R, loJ.name, lo, lidMat, true);
      R.lids.push({ n: loJ.name, ch: 'rx', shut: -(shut - open) * (o.lowerShare == null ? 0.3 : o.lowerShare) });
    }
    R.eyes.push({ j, glint, r });
    return j;
  }
  /* joint limits, as offsets from the rest pose: limit(R, 'head', { ry: [-1.2, 1.2], rx: [-0.5, 0.7] }) */
  function limit(R, name, lim) { R.limits[name] = Object.assign(R.limits[name] || {}, lim); }
  /* secondary motion: the joint follows what the clips ask of it with a lag and an overshoot (k stiffness, c damping),
     and swings with the acceleration of its own pivot (gain), as a tail, an ear or a jowl does. dir is the part's rest
     direction from the pivot, in the parent's frame; ch the rotation channel; lim clamps the swing */
  function spring(R, name, o = {}) {
    const ch = o.ch || 'rz', ax = ch === 'rx' ? [1, 0, 0] : ch === 'ry' ? [0, 1, 0] : [0, 0, 1];
    const dir = unit(o.dir || [0, -1, 0]), lever = unit(cross(ax, dir));
    R.springs.push({ n: name, ch, k: o.k == null ? 90 : o.k, c: o.c == null ? 9 : o.c, gain: o.gain == null ? 0.04 : o.gain, lever, lim: o.lim || [-0.6, 0.6],
      x: 0, v: 0, p0: null, v0: null, follow: o.follow == null ? 1 : o.follow, maxA: o.maxA == null ? 40 : o.maxA });
  }
  function finish(R) {
    for (const n of Object.keys(R.j)) {
      const o = R.j[n];
      R.rest0[n] = new Float64Array([o.position.x, o.position.y, o.position.z, o.rotation.x, o.rotation.y, o.rotation.z, o.scale.x, o.scale.y, o.scale.z]);
      R.acc[n] = new Float64Array(9);
    }
    R.names = Object.keys(R.j);
    apply(R, 0);
    R.root.updateMatrixWorld(true);
    for (const S of R.skins) {
      const skel = new THREE.Skeleton(S.bones);
      S.mesh.bind(skel, S.mesh.matrixWorld);
      for (const x of S.extra) x.bind(skel, S.mesh.matrixWorld);
      S.skeleton = skel;
    }
    for (const A of R.anims) A.mixer.update(0);
    return R;
  }
  /* after finish(): the rest pose turns (or moves) a joint without changing what a skinned mesh was bound to, so a head
     can rest turned while its neck bends smoothly into the turn */
  function restTurn(R, name, rot) {
    const r = R.rest0[name]; if (!r) return;
    r[3] += rot[0] || 0; r[4] += rot[1] || 0; r[5] += rot[2] || 0;
    apply(R, 0); R.root.updateMatrixWorld(true); glints(R);
  }
  function restMove(R, name, pos) {
    const r = R.rest0[name]; if (!r) return;
    r[0] += pos[0] || 0; r[1] += pos[1] || 0; r[2] += pos[2] || 0;
    apply(R, 0); R.root.updateMatrixWorld(true); glints(R);
  }

  /* ---- clips ---- */
  function keys(p, k) {
    if (p <= k[0][0]) return k[0][1];
    for (let i = 0; i < k.length - 1; i++) {
      const t0 = k[i][0], v0 = k[i][1], t1 = k[i + 1][0], v1 = k[i + 1][1];
      if (p <= t1) {
        const u = (p - t0) / (t1 - t0), dt = t1 - t0;
        const m0 = i > 0 ? ((v1 - k[i - 1][1]) / (t1 - k[i - 1][0])) * dt : 0;
        const m1 = i < k.length - 2 ? ((k[i + 2][1] - v0) / (k[i + 2][0] - t0)) * dt : 0;
        const u2 = u * u, u3 = u2 * u;
        return (2 * u3 - 3 * u2 + 1) * v0 + (u3 - 2 * u2 + u) * m0 + (-2 * u3 + 3 * u2) * v1 + (u3 - u2) * m1;
      }
    }
    return k[k.length - 1][1];
  }
  /* two bones in a plane: thigh L1 from the hip, shank L2; the foot aims at (tx, ty) in the hip's frame (y down the leg
     at rest). Returns [hipAngle, kneeAngle] about the plane's normal; bend picks which way the knee goes */
  function ik2(L1, L2, tx, ty, bend = 1) {
    const d = clamp(Math.hypot(tx, ty), Math.abs(L1 - L2) + 1e-6, L1 + L2 - 1e-6);
    const cosK = clamp((L1 * L1 + L2 * L2 - d * d) / (2 * L1 * L2), -1, 1), knee = PI - Math.acos(cosK);
    const a1 = Math.atan2(tx, -ty), cosA = clamp((L1 * L1 + d * d - L2 * L2) / (2 * L1 * d), -1, 1);
    return [a1 + bend * Math.acos(cosA), -bend * knee];
  }
  /* planted feet for a clip that moves the body along x: xOf(p) is the mover's x over the clip (0 at the end), steps the
     number of strides, feet the joint names (left, right), lift the foot's rise, duty the share of a stride a foot is in
     the air. While planted a foot stays where it landed on the page; it lands a little ahead and trails behind */
  function walk(o, c, p, cfg) {
    const { xOf, steps, feet } = cfg, lift = cfg.lift == null ? 0.035 : cfg.lift, duty = cfg.duty == null ? 0.38 : cfg.duty, rx = cfg.rx == null ? -3 : cfg.rx;
    const stride = cfg.stride == null ? 0.16 : cfg.stride, x = xOf(p);
    const dp = 1e-3, vel = (xOf(Math.min(1, p + dp)) - xOf(Math.max(0, p - dp))) / (2 * dp), dirn = vel < -1e-6 ? -1 : vel > 1e-6 ? 1 : 0;
    const out = [];
    for (let k = 0; k < feet.length; k++) {
      const ph = (p * steps + k / feet.length) % 1, i = Math.floor(p * steps + k / feet.length);
      const landP = (i - k / feet.length) / steps, nextLand = (i + 1 - k / feet.length) / steps;
      let off, up = 0, tilt = 0;
      const speedAt = (pp) => { const v = (xOf(clamp(pp + dp, 0, 1)) - xOf(clamp(pp - dp, 0, 1))) / (2 * dp); return v; };
      const ahead = (pp) => { const v = speedAt(pp), s = clamp(Math.abs(v) / (steps * 1.4), 0, 1); return Math.sign(v) * stride * 0.5 * s; };
      if (ph < 1 - duty) {
        const pl = clamp(landP, 0, 1);
        off = ahead(pl) + xOf(pl) - x;
      } else {
        const u = (ph - (1 - duty)) / duty, pl = clamp(landP, 0, 1), pn = clamp(nextLand, 0, 1);
        const from = ahead(pl) + xOf(pl) - x, to = ahead(pn) + xOf(pn) - x;
        off = lerp(from, to, u * u * (3 - 2 * u));
        up = Math.sin(u * PI) * lift * clamp(Math.abs(speedAt(p)) / (steps * 0.7) + 0.15, 0, 1);
        tilt = Math.sin(u * PI) * rx * lift;
      }
      if (dirn === 0 && Math.abs(off) < 1e-6) off = 0;
      o(feet[k], 'px', off); o(feet[k], 'py', up); if (tilt) o(feet[k], 'rx', tilt);
      out.push(off);
    }
    return out;
  }
  const HELP = {
    PI, TAU, clamp, lerp, sst, keys, ik2,
    env: (p, a = 0.15, b = 0.25) => sst(0, a, p) * (1 - sst(1 - b, 1, p)),
    bump: (p, a, b) => { if (p <= a || p >= b) return 0; const s = Math.sin((PI * (p - a)) / (b - a)); return s * s; },
    ramp: (p, a, b) => sst(a, b, p),
    hop: (p, a, b) => { if (p <= a || p >= b) return 0; const u = (p - a) / (b - a); return 4 * u * (1 - u); },
    wave: (p, n, ph = 0) => Math.sin(TAU * (n * p + ph)),
    walk: (o, p, cfg) => walk(o, null, p, cfg),
  };
  function addTo(R, n, ch, v) {
    if (n === 'ctl') {
      const c = R.ctl;
      if (ch === 'lid' || ch === 'look') { if (v > c[ch]) c[ch] = v; } else c[ch] += v;
      return;
    }
    const a = R.acc[n];
    if (!a) return;
    if (ch === 's') { a[6] += v; a[7] += v; a[8] += v; } else a[CH[ch]] += v;
  }
  function apply(R, lid) {
    for (const L of R.lids) addTo(R, L.n, L.ch, L.shut * lid);
    for (let i = 0; i < R.names.length; i++) {
      const n = R.names[i], o = R.j[n], r = R.rest0[n], a = R.acc[n], L = R.limits[n];
      if (L) for (const ch in L) { const k = CH[ch]; if (k != null) a[k] = clamp(a[k], L[ch][0], L[ch][1]); }
      o.position.set(r[0] + a[0], r[1] + a[1], r[2] + a[2]);
      o.rotation.set(r[3] + a[3], r[4] + a[4], r[5] + a[5]);
      o.scale.set(r[6] * (1 + a[6]), r[7] * (1 + a[7]), r[8] * (1 + a[8]));
    }
    if (R.anims.length) animate(R);
    if (R.shadow) {
      const m = R.j.mover.position, k = 1 / (1 + 3 * Math.max(0, m.y));
      R.shadow.position.set(m.x + R.shadowAt[0], 0.002, m.z + R.shadowAt[1]);
      R.shadow.scale.set(R.shadowR[0] * k, 1, R.shadowR[1] * k);
      R.shadow.material.uniforms.uA.value = R.shadowA * k * k;
    }
  }
  /* a soft contact shadow of the companion's own (a stage draws one too; a companion keeps its own by setting it) */
  function shadow(R, at, radii, alpha) {
    const g = new THREE.PlaneGeometry(2, 2);
    g.rotateX(-PI / 2);
    const m = new THREE.ShaderMaterial({
      transparent: true, depthWrite: false, uniforms: { uA: { value: alpha } },
      vertexShader: 'varying vec2 vU; void main(){ vU = uv * 2.0 - 1.0; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }',
      fragmentShader: 'uniform float uA; varying vec2 vU; void main(){ float r = length(vU); float a = uA * pow(max(1.0 - r, 0.0), 1.7); gl_FragColor = vec4(0.09, 0.08, 0.07, a); }',
    });
    const s = new THREE.Mesh(g, m);
    s.renderOrder = -1;
    R.root.add(s);
    R.shadow = s; R.shadowAt = at; R.shadowR = radii; R.shadowA = alpha; R.geos.push(g); R.mats.add(m);
  }
  function play(R, name, variant) {
    const def = R.clips[name];
    if (!def) return 0;
    const cur = R.cur;
    if (cur && !cur.done && cur.name === name && (name === 'dance' || name === 'talk' || name === 'rest')) return Math.max(0, cur.dur - cur.t);
    const nv = def.variants || 1;
    const v = variant != null ? ((variant % nv) + nv) % nv : nv > 1 ? Math.floor(R.rnd() * nv) : 0;
    const dur = typeof def.dur === 'function' ? def.dur(v) : def.dur;
    if (cur && !cur.done) { cur.fade = 1; R.fading.push(cur); }
    R.cur = { name, def, dur, t: 0, done: false, fin: R.fading.length ? 0 : 1, ctx: Object.assign({ v, r: R.rnd() }, HELP) };
    if (IDLES.includes(name)) R.lastIdle = name;
    return dur;
  }
  function run(R, c, dt, add, fading) {
    c.t += dt;
    let p = c.t / c.dur;
    if (p >= 1) { p = 1; c.done = true; }
    let w = 1;
    if (fading) {
      c.fade -= dt / (c.def.fadeOut || 0.25);
      if (c.fade <= 0) { c.done = true; if (c.def.action) c.def.action.weight = 0; return; }
      w = sst(0, 1, c.fade);
    } else if (c.fin < 1) { c.fin = Math.min(1, c.fin + dt / 0.25); w = sst(0, 1, c.fin); }
    if (c.def.action) { c.def.action.time = p * c.def.clipDur; c.def.action.weight = w * (c.def.weight == null ? 1 : c.def.weight); }
    if (c.def.fn) c.def.fn(p, w === 1 ? add : (n, ch, x) => add(n, ch, x * w), c.ctx);
  }
  const gap = (R) => 2.5 + R.rnd() * 4.5;
  function schedule(R, st) {
    const cur = R.cur, busy = !!(cur && !cur.done), name = busy ? cur.name : '';
    const idle = st.idleFor || 0;
    if (st.helpOpen) {
      if (!busy || IDLES.includes(name) || name === 'rest') play(R, 'talk');
      return;
    }
    if (name === 'rest' && idle < 1) { play(R, 'notice'); R.nextIdle = R.t + 1.3 + gap(R); return; }
    if (busy) return;
    if (idle > REST_AFTER) { play(R, 'rest'); return; }
    if (st.scrolling || R.t < R.nextIdle) return;
    const pool = (R.spec.idles || IDLES).filter((n) => n !== R.lastIdle && R.clips[n]);
    if (!pool.length) return;
    const d = play(R, pool[Math.floor(R.rnd() * pool.length)]);
    R.nextIdle = R.t + d + gap(R);
  }
  function attend(R, dt, st) {
    const L = R.look, S = R.spec.look || { yaw: 0.6, pitch: 0.3 }, P = st.pointer;
    if (P && (L.px === null || Math.abs(P.x - L.px) + Math.abs(P.y - L.py) > 0.04)) {
      L.px = P.x; L.py = P.y; L.until = R.t + 1.4 + R.rnd() * 1.8;
      L.ty = clamp(P.x * 0.6, -1, 1) * S.yaw;
      L.tp = -clamp(P.y * 0.6, -1, 1) * S.pitch;
    }
    if (!P) L.px = L.py = null;
    if (R.t > L.until) { L.ty = 0; L.tp = 0; }
    if (S.snap) {
      L.hold -= dt;
      if (L.hold <= 0) { L.sy = L.ty; L.sp = L.tp; L.hold = 0.25 + R.rnd() * 0.6; }
      const k = 1 - Math.exp(-dt * 36);
      L.y += (L.sy - L.y) * k; L.p += (L.sp - L.p) * k;
    } else {
      const w = S.speed || 7;
      L.vy += (w * w * (L.ty - L.y) - 2 * w * L.vy) * dt; L.y += L.vy * dt;
      L.vp += (w * w * (L.tp - L.p) - 2 * w * L.vp) * dt; L.p += L.vp * dt;
    }
  }
  function blinks(R, dt) {
    if (R.blinkT < 0 && R.t >= R.nextBlink) {
      R.blinkT = 0;
      if (R.blinkAgain) { R.blinkAgain = false; R.nextBlink = R.t + 2.5 + R.rnd() * 3.5; }
      else if (R.rnd() < 0.14) { R.blinkAgain = true; R.nextBlink = R.t + 0.3; }
      else R.nextBlink = R.t + 2.5 + R.rnd() * 3.5;
    }
    if (R.blinkT < 0) return 0;
    R.blinkT += dt;
    const t = R.blinkT, s = R.spec.blinkSpeed || 1, a = 0.07 * s, b = 0.11 * s, e = 0.26 * s;
    if (t >= e) { R.blinkT = -1; return 0; }
    return t < a ? sst(0, a, t) : t < b ? 1 : 1 - sst(b, e, t);
  }
  /* springs: run after the clips have accumulated, before apply. Each spring replaces the clip's own value on its channel
     with a sprung one: it follows that value with lag and overshoot, and swings with its pivot's acceleration */
  function springs(R, dt) {
    const T = R.tmp;
    for (const S of R.springs) {
      const a = R.acc[S.n], j = R.j[S.n];
      if (!a || !j) continue;
      const target = a[CH[S.ch]] * S.follow;
      j.getWorldPosition(T.v);
      let drive = 0;
      if (S.p0 && dt > 0) {
        T.v2.copy(T.v).sub(S.p0).divideScalar(dt);
        if (S.v0) {
          const acc = T.v3.copy(T.v2).sub(S.v0).divideScalar(dt);
          const par = j.parent;
          if (par) { par.getWorldQuaternion(T.q); acc.applyQuaternion(T.q.invert()); }
          drive = clamp(-(acc.x * S.lever[0] + acc.y * S.lever[1] + acc.z * S.lever[2]), -S.maxA, S.maxA) * S.gain;
        }
        S.v0 = S.v0 || new THREE.Vector3(); S.v0.copy(T.v2);
      }
      S.p0 = S.p0 || new THREE.Vector3(); S.p0.copy(T.v);
      const h = Math.min(dt, 1 / 30);
      S.v += (S.k * (target - S.x) - S.c * S.v + drive * S.k * 0.25) * h;
      S.x += S.v * h;
      S.x = clamp(S.x, S.lim[0] + target, S.lim[1] + target);
      a[CH[S.ch]] = S.x;
    }
  }
  /* eye glints sit on the cornea toward the light and the viewer */
  function glints(R) {
    if (!R.eyes.length) return;
    const T = R.tmp, L = K.view.L, V = K.view.V;
    T.v.copy(L).multiplyScalar(0.72).addScaledVector(V, 0.5).normalize();
    for (const E of R.eyes) {
      E.j.getWorldQuaternion(T.q);
      T.v2.copy(T.v).applyQuaternion(T.q.invert());
      if (T.v2.z < 0.35) { T.v2.z = 0.35; T.v2.normalize(); }
      E.glint.position.copy(T.v2).multiplyScalar(E.r * 1.0);
      E.glint.quaternion.setFromUnitVectors(T.z, T.v2);
    }
  }
  function update(R, dt, st) {
    st = st || {};
    dt = dt > 0 ? Math.min(dt, 0.1) : 0;
    for (let i = 0; i < R.names.length; i++) R.acc[R.names[i]].fill(0);
    const c = R.ctl;
    c.lid = 0; c.look = 0; c.breath = 0; c.amp = 0;
    const add = (n, ch, v) => addTo(R, n, ch, v);
    if (st.motion && st.motion !== 'on') {
      R.cur = null; R.fading.length = 0; R.duck = 0;
      for (const S of R.springs) { S.x = 0; S.v = 0; S.p0 = null; S.v0 = null; }
      for (const A of R.anims) for (const act of A.actions) act.weight = 0;
      if (R.spec.life) R.spec.life(add, { b: 0.35, yaw: 0, pitch: 0, t: R.t, still: true });
      apply(R, 0);
      R.root.updateMatrixWorld(true);
      glints(R);
      return;
    }
    R.t += dt;
    if (!R.check) schedule(R, st);
    for (const f of R.fading) run(R, f, dt, add, true);
    if (R.fading.length) R.fading = R.fading.filter((f) => !f.done);
    if (R.cur) {
      run(R, R.cur, dt, add, false);
      if (R.cur.done) { if (R.cur.def.action) R.cur.def.action.weight = 0; R.cur = null; R.nextIdle = Math.max(R.nextIdle, R.t + gap(R)); }
    }
    let blink = 0;
    if (!R.check) {
      const rate = (R.spec.breath || 0.3) * Math.max(0.2, 1 + c.breath) * (1 + 0.13 * Math.sin(R.t * 0.29) + 0.07 * Math.sin(R.t * 0.71 + 1.3));
      R.phase += dt * TAU * rate;
      attend(R, dt, st);
      blink = blinks(R, dt);
      const k = 1 - Math.min(1, c.look);
      if (R.spec.life) R.spec.life(add, { b: Math.sin(R.phase) * (1 + c.amp), yaw: R.look.y * k, pitch: R.look.p * k, t: R.t, still: false });
      const tgt = st.scrolling ? 1 : 0;
      R.duck += (tgt - R.duck) * (1 - Math.exp(-dt * (tgt > R.duck ? 12 : 3.5)));
      if (R.duck > 1e-4) {
        if (R.spec.duck) R.spec.duck(add, R.duck);
        else { add('mover', 'px', 0.36 * R.duck); add('pose', 'ry', 0.45 * R.duck); }
      }
    }
    if (R.springs.length && !R.noSprings) springs(R, dt);
    apply(R, Math.max(blink, c.lid));
    R.root.updateMatrixWorld(true);
    glints(R);
  }
  function rest(R) {
    R.cur = null; R.fading.length = 0; R.duck = 0; R.blinkT = -1;
    const L = R.look;
    L.y = L.p = L.vy = L.vp = L.ty = L.tp = L.sy = L.sp = 0;
    for (let i = 0; i < R.names.length; i++) R.acc[R.names[i]].fill(0);
    R.ctl.lid = R.ctl.look = R.ctl.breath = R.ctl.amp = 0;
    for (const S of R.springs) { S.x = 0; S.v = 0; S.p0 = null; S.v0 = null; }
    for (const A of R.anims) for (const act of A.actions) act.weight = 0;
    apply(R, 0);
    R.root.updateMatrixWorld(true);
    glints(R);
  }

  /* ---------- downloaded models ---------- */
  const base = opts.base || (typeof document !== 'undefined' ? document.baseURI : './');
  /* a small OBJ reader: v, vn, vt, f (any polygon, fanned); one geometry, normals computed when the file has none */
  function parseOBJ(text) {
    const V = [], N = [], T = [], P = [], NN = [], UV = [];
    const idx = (s, n) => { let i = parseInt(s, 10); if (isNaN(i)) return -1; if (i < 0) i += n / 3 + 1; return i - 1; };
    let hasN = false, hasT = false;
    for (const raw of text.split(/\r?\n/)) {
      const line = raw.trim();
      if (!line || line[0] === '#') continue;
      const parts = line.split(/\s+/), k = parts[0];
      if (k === 'v') V.push(+parts[1], +parts[2], +parts[3]);
      else if (k === 'vn') N.push(+parts[1], +parts[2], +parts[3]);
      else if (k === 'vt') T.push(+parts[1], +(parts[2] || 0));
      else if (k === 'f') {
        const vs = parts.slice(1).map((w) => w.split('/'));
        for (let i = 1; i < vs.length - 1; i++) for (const w of [vs[0], vs[i], vs[i + 1]]) {
          const vi = idx(w[0], V.length);
          P.push(V[3 * vi], V[3 * vi + 1], V[3 * vi + 2]);
          if (w[1]) { const ti = idx(w[1], T.length * 1.5); if (ti >= 0) { UV.push(T[2 * ti], T[2 * ti + 1]); hasT = true; } }
          if (w[2]) { const ni = idx(w[2], N.length); if (ni >= 0) { NN.push(N[3 * ni], N[3 * ni + 1], N[3 * ni + 2]); hasN = true; } }
        }
      }
    }
    const g = new THREE.BufferGeometry();
    g.setAttribute('position', new THREE.Float32BufferAttribute(P, 3));
    if (hasN && NN.length === P.length) g.setAttribute('normal', new THREE.Float32BufferAttribute(NN, 3)); else g.computeVertexNormals();
    if (hasT && UV.length * 1.5 === P.length) g.setAttribute('uv', new THREE.Float32BufferAttribute(UV, 2));
    return g;
  }
  /* loads a glTF, GLB or OBJ under kit.base (or an absolute address) and resolves { scene, animations } */
  async function loadModel(url, o = {}) {
    const abs = new URL(url, base).href;
    if (/\.obj(\?|$)/i.test(abs)) {
      const res = await fetch(abs, { credentials: 'omit' });
      if (!res.ok) throw new Error('model ' + res.status);
      const geo = parseOBJ(await res.text());
      const m = new THREE.Mesh(geo, physical(Object.assign({ vertexColors: false, color: 0xbbbbbb }, o.mat || {})));
      m.name = o.name || 'obj'; m.castShadow = true; m.receiveShadow = true; m.frustumCulled = false;
      const g = new THREE.Group(); g.add(m);
      return { scene: g, animations: [], meshes: [m] };
    }
    let L = loaders.GLTFLoader;
    if (!L && loaders.gltf) { const mod = await loaders.gltf(); L = mod.GLTFLoader || mod.default; }
    if (!L) throw new Error('no glTF loader was given to the kit');
    const loader = new L();
    const gltf = await loader.loadAsync(abs);
    const meshes = [];
    gltf.scene.traverse((x) => { if (x.isMesh) { x.frustumCulled = false; x.castShadow = true; x.receiveShadow = true; meshes.push(x); } });
    return { scene: gltf.scene, animations: gltf.animations || [], meshes, gltf };
  }
  /* wraps a model so it stands one unit tall (or o.height), feet at y = 0, centred, turned by o.yaw to face +z */
  function fit(root, o = {}) {
    const holder = new THREE.Group(); holder.name = 'fit';
    root.rotation.y = o.yaw || 0; root.updateMatrixWorld(true);
    const box = new THREE.Box3().setFromObject(root), size = new THREE.Vector3(); box.getSize(size);
    const extent = o.axis === 'z' ? size.z : o.axis === 'x' ? size.x : size.y;
    const s = (o.height || 1) / (extent || 1);
    holder.add(root); root.scale.setScalar(s); root.updateMatrixWorld(true);
    const b2 = new THREE.Box3().setFromObject(root), c = new THREE.Vector3(); b2.getCenter(c);
    root.position.set(-c.x + (o.dx || 0), -b2.min.y + (o.dy || 0), -c.z + (o.dz || 0));
    root.updateMatrixWorld(true);
    holder.userData.box = new THREE.Box3().setFromObject(root);
    return holder;
  }
  /* every material of a model becomes the kit's physical material (its maps kept) with the given sheen and clearcoat */
  function dress(root, o = {}) {
    const out = [];
    root.traverse((x) => {
      if (!x.isMesh) return;
      const old = Array.isArray(x.material) ? x.material[0] : x.material;
      const m = physical(Object.assign({
        vertexColors: !!(x.geometry.attributes.color), color: old && old.color ? old.color.getHex() : 0xffffff,
        map: old && old.map || null, normalMap: old && old.normalMap || null, roughMap: old && old.roughnessMap || null,
        rough: old && old.roughness != null ? old.roughness : 0.7, transparent: !!(old && old.transparent), opacity: old && old.opacity != null ? old.opacity : 1,
        side: old && old.side != null ? old.side : THREE.FrontSide,
      }, o.mat || {}, typeof o.per === 'function' ? (o.per(x) || {}) : {}));
      if (old && old.normalScale && m.normalMap) m.normalScale.copy(old.normalScale);
      if (old && old.alphaTest) m.alphaTest = old.alphaTest;
      tune(m, x.geometry);
      x.material = m; x.frustumCulled = false; x.castShadow = true; x.receiveShadow = true;
      out.push(x);
    });
    return out;
  }
  /* the bones of a model by name, and a flat list */
  function bonesOf(root) {
    const map = {}, list = [];
    root.traverse((x) => { if (x.isBone) { map[x.name] = x; list.push(x); } });
    return { map, list };
  }
  /* a model's own animation becomes a clip of the rig: anim(R, 'arrive', clip, root, { dur, fn }). The clip plays on an
     AnimationMixer over the model, scaled to dur; fn (optional) adds procedural channels on top, and the rig's own look,
     breathing and springs ride on top of it */
  function anim(R, name, clip, root, o = {}) {
    let A = R.anims.find((a) => a.root === root);
    if (!A) { A = { root, mixer: new THREE.AnimationMixer(root), actions: [], touched: new Set() }; R.anims.push(A); }
    const action = A.mixer.clipAction(clip);
    action.play(); action.weight = 0; action.paused = true; action.enabled = true;
    A.actions.push(action);
    for (const tr of clip.tracks) { const nm = THREE.PropertyBinding.parseTrackName(tr.name).nodeName; if (nm) A.touched.add(nm); }
    R.clips[name] = Object.assign({ dur: o.dur || clip.duration, clipDur: clip.duration, action, weight: o.weight, fn: o.fn, variants: o.variants, fadeOut: o.fadeOut }, {});
    return R.clips[name];
  }
  function animate(R) {
    for (const A of R.anims) {
      A.mixer.update(0);
      /* the mixer wrote absolute poses on the bones it drives; the rig's channels are added back on top */
      for (const n of A.touched) {
        const j = R.j[n], a = R.acc[n];
        if (!j || !a) continue;
        j.position.x += a[0]; j.position.y += a[1]; j.position.z += a[2];
        j.rotation.x += a[3]; j.rotation.y += a[4]; j.rotation.z += a[5];
      }
    }
  }

  /* ---------- the stage: lights, environment, camera framing, shadows, parallax ---------- */
  const view = { L: new THREE.Vector3(-0.45, 0.72, 0.53).normalize(), V: new THREE.Vector3(0, 0.1, 1).normalize() };
  function contactShadow() {
    const c = document.createElement('canvas'); c.width = c.height = 64;
    const g = c.getContext('2d'), r = g.createRadialGradient(32, 32, 2, 32, 32, 31);
    r.addColorStop(0, 'rgba(0,0,0,.46)'); r.addColorStop(0.55, 'rgba(0,0,0,.18)'); r.addColorStop(1, 'rgba(0,0,0,0)'); g.fillStyle = r; g.fillRect(0, 0, 64, 64);
    const t = new THREE.CanvasTexture(c);
    const m = new THREE.Mesh(new THREE.PlaneGeometry(1, 1), new THREE.MeshBasicMaterial({ map: t, transparent: true, depthWrite: false, toneMapped: false }));
    m.rotation.x = -PI / 2; m.position.y = 0.0015; m.renderOrder = -2; m.name = 'contact-shadow';
    return m;
  }
  function stage(renderer, o = {}) {
    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(o.fov || 34, 1, 0.03, 40);
    const hemi = new THREE.HemisphereLight(0xfff5ea, 0x6a6258, 0.6);
    const key = new THREE.DirectionalLight(0xfff0dc, 2.3); key.position.set(-1.7, 3.1, 2.6);
    const fill = new THREE.DirectionalLight(0xe9e7e2, 0.65); fill.position.set(2.6, 1.3, 2.2);
    const rim = new THREE.DirectionalLight(0xffffff, 1.35); rim.position.set(1.1, 2.4, -2.8);
    scene.add(hemi, key, fill, rim);
    key.shadow.mapSize.set(512, 512); key.shadow.camera.near = 0.5; key.shadow.camera.far = 9;
    key.shadow.camera.left = key.shadow.camera.bottom = -1.1; key.shadow.camera.right = key.shadow.camera.top = 1.1;
    key.shadow.bias = -0.0006; key.shadow.normalBias = 0.02; key.shadow.radius = 3;
    const contact = contactShadow(); scene.add(contact);
    renderer.toneMapping = THREE.ACESFilmicToneMapping; renderer.toneMappingExposure = o.exposure || 1.0;
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    renderer.shadowMap.type = THREE.PCFSoftShadowMap;
    let env = null, pmrem = null;
    const S = {
      scene, camera, key, fill, rim, hemi, contact, target: new THREE.Vector3(), basePos: new THREE.Vector3(), yaw: 0, pitch: 0, dark: false,
      /* the environment light: a room's soft reflections, made once */
      setEnv(on) {
        if (on && !env) {
          try {
            const Room = loaders.RoomEnvironment;
            pmrem = new THREE.PMREMGenerator(renderer);
            if (Room) { const room = new Room(); env = pmrem.fromScene(room, 0.04).texture; room.traverse((x) => { if (x.geometry) x.geometry.dispose(); if (x.material) x.material.dispose(); }); }
            else {
              const eq = tex.canvas(64, 32, (g, w, h) => { const gr = g.createLinearGradient(0, 0, 0, h); gr.addColorStop(0, '#dfe2e6'); gr.addColorStop(0.5, '#b9b4ab'); gr.addColorStop(1, '#4a4440'); g.fillStyle = gr; g.fillRect(0, 0, w, h); g.fillStyle = '#fff6e8'; g.fillRect(w * 0.1, h * 0.2, w * 0.18, h * 0.3); });
              eq.mapping = THREE.EquirectangularReflectionMapping; env = pmrem.fromEquirectangular(eq).texture; eq.dispose();
            }
            pmrem.dispose(); pmrem = null;
          } catch (e) { env = null; }
        }
        scene.environment = on && env ? env : null;
        scene.environmentIntensity = o.envIntensity || 0.5;
        return !!scene.environment;
      },
      setTier(t) {
        const c = caps(t);
        const shadows = c.shadow > 0 && o.shadows !== false;
        if (shadows !== key.castShadow) { key.castShadow = shadows; renderer.shadowMap.enabled = shadows; if (shadows) key.shadow.mapSize.set(c.shadow, c.shadow); renderer.shadowMap.needsUpdate = true; }
        S.setEnv(c.env && o.env !== false);
        hemi.intensity = scene.environment ? 0.6 : 1.1;
        fill.intensity = scene.environment ? 0.65 : 0.9;
      },
      /* on a dark page the rim grows, so black fur and feathers keep an edge */
      setDark(d) { S.dark = !!d; rim.intensity = d ? 2.1 : 1.35; hemi.intensity = (scene.environment ? 0.6 : 1.1) * (d ? 1.15 : 1); },
      /* frame: the box fr {x:[a,b], y:[a,b]} (root units) must fill the dock's rectangle, which sits inside the canvas:
         rect = {W, H, dockW, dockH, pad (px between the dock's bottom and the canvas's), perch (bool)} in CSS px */
      frame(fr, rect, fov) {
        const W = Math.max(1, rect.W), H = Math.max(1, rect.H), dW = rect.dockW || W, dH = rect.dockH || H, pad = rect.pad || 0;
        camera.aspect = W / H; camera.fov = fov || o.fov || 34;
        const mx = rect.perch ? 0.05 : 0.04, my = rect.perch ? 0.16 : 0.06;
        const [x0, x1] = fr.x, [y0, y1] = fr.y, bw = Math.max(x1 - x0, 0.2), bh = Math.max(y1 - y0, 0.2);
        const vDock = Math.max(bh / (1 - my), (bw / (1 - 2 * mx)) * (dH / dW) / 1);
        const V = vDock * (H / dH);
        const yb = y0 - V * (pad / H), cy = yb + V / 2, cx = (x0 + x1) / 2;
        const dist = (V / 2) / Math.tan(THREE.MathUtils.degToRad(camera.fov / 2));
        S.target.set(cx, cy, 0);
        S.basePos.set(cx, cy + V * (rect.perch ? 0.04 : 0.09), dist + (rect.z || 0));
        S.look(S.yaw, S.pitch);
        camera.updateProjectionMatrix();
        contact.scale.set(bw * 1.15, 1, Math.max(bw * 0.55, 0.3));
        contact.position.x = cx;
        S.view = { V, cx, cy, yb, dist };
        return S.view;
      },
      /* pointer parallax: the camera swings a little around the animal (radians) */
      look(yaw, pitch) {
        S.yaw = yaw || 0; S.pitch = pitch || 0;
        const p = S.basePos, t = S.target, dx = p.x - t.x, dy = p.y - t.y, dz = p.z - t.z, r = Math.hypot(dx, dz);
        const a = Math.atan2(dx, dz) + S.yaw;
        camera.position.set(t.x + Math.sin(a) * r, dy + t.y + Math.tan(S.pitch) * r * 0.5, t.z + Math.cos(a) * r);
        camera.lookAt(t);
      },
      render(root) {
        if (root) { key.target.position.copy(root.position); key.target.updateMatrixWorld(); }
        view.L.copy(key.position).normalize();
        view.V.copy(camera.position).sub(S.target).normalize();
        renderer.render(scene, camera);
      },
      dispose() {
        try { if (env) env.dispose(); if (pmrem) pmrem.dispose(); contact.material.map.dispose(); contact.material.dispose(); contact.geometry.dispose(); } catch (e) {}
      },
    };
    S.setTier(o.tier == null ? tier : o.tier);
    return S;
  }

  /* ---------- the kit ---------- */
  const K = {
    THREE, version: '1.0', PI, TAU, clamp, lerp, sst, random, noise, fbm, rgb, mixc, lin, hex, unit, cross, dot,
    sd, surf, strip, circle, prim, hit, tex, physical, mat, tune, fur,
    rig, joint, local, adopt, put, skin, autoSkin, eye, limit, spring, shadow, finish, restTurn, restMove, update, play, rest, keys, ik2, walk, HELP, stats,
    loadModel, parseOBJ, fit, dress, bonesOf, anim,
    stage, view, caps, setTier, onTier: (f) => { tierFns.add(f); return () => tierFns.delete(f); },
    get tier() { return tier; }, get base() { return base; }, set seed(s) { seedNext = s; }, get seed() { return seedNext; },
  };
  return K;
}
export default createKit;
