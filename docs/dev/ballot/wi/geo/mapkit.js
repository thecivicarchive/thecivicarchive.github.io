/* The ballot map (John, 2026-10-01). One map for every kind of line a ballot is made of, drawn in Web Mercator from the
   state's own map files (geo/index.json says what they are) with the reader that was built with them (geo/reader.js, MNGeo).
   A layer's own file is drawn while the view is far out; closer in, the precinct file of each county in view takes over, so
   the lines are the precincts' own down to a street. Nothing here asks any other server for anything, with one exception a
   reader has to switch on: the street pictures, which are OpenStreetMap's.
   No pointer capture anywhere: drags and pinches are followed with listeners on the window, dropped when the map goes. */
(function () {
"use strict";
const TILE = 256, MAXZ = 18, TILEZ = 19, TILES = "https://tile.openstreetmap.org/";
const mx = lon => (lon + 180) / 360 * TILE;
const my = lat => { const s = Math.sin(Math.max(-85, Math.min(85, lat)) * Math.PI / 180); return (.5 - Math.log((1 + s) / (1 - s)) / (4 * Math.PI)) * TILE; };
const lonAt = x => x / TILE * 360 - 180;
const latAt = y => Math.atan(Math.sinh(Math.PI * (1 - 2 * y / TILE))) * 180 / Math.PI;
const holds = (v, id) => Array.isArray(v) ? v.indexOf(id) >= 0 : v === id;

function BallotMap(el, opt) {
  const IDX = opt.index, base = opt.base, q = opt.v ? "?v=" + opt.v : "";
  const canvas = el.querySelector("canvas"), ctx = canvas.getContext("2d");
  const tilesEl = el.querySelector(".gtiles"), pinEl = el.querySelector(".gpin"), attrEl = el.querySelector(".gattr"), busyEl = el.querySelector(".gbusy");
  const LAYER = {}, COUNTY = {};
  IDX.layers.forEach(L => { LAYER[L.kind] = L; });
  IDX.counties.forEach(c => { COUNTY[c.id] = c; });
  const KINDS = IDX.arc_kinds || [], bit = kind => { const i = KINDS.indexOf(kind); return i < 0 ? 0 : 1 << i; };
  const files = {}, waits = {}, failed = {}, tiles = new Map();
  const off = new AbortController(), sig = {signal: off.signal};
  let W = 0, H = 0, dpr = 1, view = null, fit = null, layer = LAYER[opt.layer] ? opt.layer : "county", sel = null, mine = null, pin = null,
    streets = false, dead = false, polls = null, sched = 0, tileTimer = 0, tilePending = 0, lastType = "", keys = false;

  /* ----- the files: each fetched once, its lines turned into map units once ----- */
  function world(f) {
    const t = f.transform, sx = t.scale[0], sy = t.scale[1], tx = t.translate[0], ty = t.translate[1];
    f._w = f._lines.map(L => { const a = new Float64Array(L.length); for (let k = 0; k < L.length; k += 2) { a[k] = mx(L[k] * sx + tx); a[k + 1] = my(L[k + 1] * sy + ty); } return a; });
    f._wb = f._w.map(a => { let x0 = 1e9, y0 = 1e9, x1 = -1e9, y1 = -1e9;
      for (let k = 0; k < a.length; k += 2) { if (a[k] < x0) x0 = a[k]; if (a[k] > x1) x1 = a[k]; if (a[k + 1] < y0) y0 = a[k + 1]; if (a[k + 1] > y1) y1 = a[k + 1]; }
      return [x0, y0, x1, y1]; });
    return f;
  }
  const busy = () => { if (busyEl) busyEl.hidden = !Object.keys(waits).length; };
  function load(path) {
    if (files[path]) return Promise.resolve(files[path]);
    if (!waits[path]) {
      waits[path] = fetch(base + path + q).then(r => r.ok ? r.json() : Promise.reject(new Error(path + ": " + r.status)))
        .then(d => { files[path] = world(MNGeo.open(d)); delete waits[path]; busy(); if (!dead) schedule(); return files[path]; },
          e => { delete waits[path]; failed[path] = Date.now(); busy(); throw e; });
      busy();
    }
    return waits[path];
  }
  const want = path => { if (!files[path] && !waits[path] && !(failed[path] && Date.now() - failed[path] < 8000)) load(path).catch(() => {}); return files[path] || null; };
  const schoolPath = id => IDX.school.files.replace("<id>", id);
  const byId = (f, kind) => f._ids || (f._ids = Object.fromEntries(f.objects[kind].geometries.map(g => [g.id, g])));
  function rings(f, g) {      // a shape's rings in map units, kept on the shape
    if (g._wr) return g._wr;
    const out = [];
    for (const poly of MNGeo.polygons(f, g)) for (const ring of poly) { const a = new Float64Array(ring.length * 2);
      for (let i = 0; i < ring.length; i++) { a[2 * i] = mx(ring[i][0]); a[2 * i + 1] = my(ring[i][1]); } out.push(a); }
    return g._wr = out;
  }

  /* ----- the view: its middle in map units, and a zoom ----- */
  const scale = () => Math.pow(2, view.z);
  const X = x => (x - view.x) * scale() + W / 2, Y = y => (y - view.y) * scale() + H / 2;
  const lonLat = (px, py) => [lonAt(view.x + (px - W / 2) / scale()), latAt(view.y + (py - H / 2) / scale())];
  const bounds = () => { const a = lonLat(0, H), b = lonLat(W, 0); return [a[0], a[1], b[0], b[1]]; };
  function fitTo(b, pad, most) {
    const x0 = mx(b[0]), x1 = mx(b[2]), y0 = my(b[3]), y1 = my(b[1]);
    const z = Math.log2(Math.min((W - 2 * pad) / Math.max(1e-9, x1 - x0), (H - 2 * pad) / Math.max(1e-9, y1 - y0)));
    return {x: (x0 + x1) / 2, y: (y0 + y1) / 2, z: Math.min(most || MAXZ, z)};
  }
  function clamp(v) {
    const b = IDX.bbox;
    v.z = Math.max(fit.z, Math.min(MAXZ, v.z));
    if (v.z <= fit.z + .01) { v.x = fit.x; v.y = fit.y; return v; }
    v.x = Math.max(mx(b[0]), Math.min(mx(b[2]), v.x)); v.y = Math.max(my(b[3]), Math.min(my(b[1]), v.y));
    return v;
  }
  function setView(v) { view = clamp({x: v.x, y: v.y, z: v.z}); schedule(); }
  function zoomTo(z, px, py) {
    z = Math.max(fit.z, Math.min(MAXZ, z));
    if (px == null) { px = W / 2; py = H / 2; }
    const k0 = scale(), wx = view.x + (px - W / 2) / k0, wy = view.y + (py - H / 2) / k0, k1 = Math.pow(2, z);
    setView({x: wx - (px - W / 2) / k1, y: wy - (py - H / 2) / k1, z});
  }
  const stepIn = (px, py) => zoomTo(Math.floor(view.z + 1e-6) + 1, px, py);      // whole steps, so the street pictures stay sharp
  const stepOut = (px, py) => zoomTo(Math.ceil(view.z - 1e-6) - 1, px, py);
  function schedule() {      // one drawing for however many changes; a timer stands in where a page that is not showing gets no frames
    if (sched || dead) return;
    sched = 1; let done = false;
    const run = () => { if (done) return; done = true; sched = 0; draw(); };
    requestAnimationFrame(run); setTimeout(run, 60);
  }
  function resize() {
    const r = el.getBoundingClientRect(), w = Math.round(r.width), h = Math.round(r.height);
    if (!w || !h || (w === W && h === H)) return;
    const whole = !view || Math.abs(view.z - fit.z) < .01;
    W = w; H = h; dpr = Math.min(2.5, window.devicePixelRatio || 1);
    canvas.width = Math.round(W * dpr); canvas.height = Math.round(H * dpr);
    fit = fitTo(IDX.bbox, 12);
    view = whole ? {x: fit.x, y: fit.y, z: fit.z} : clamp(view);
    draw();
  }

  /* ----- what the view needs: the layer's own file far out; each county's precinct file close in ----- */
  function plan() {
    const L = LAYER[layer] || {}, b = bounds(), close = view.z >= (L.good_to_zoom || 10.5) + .9;
    const cs = close ? IDX.counties.filter(c => c.bbox[0] <= b[2] && c.bbox[2] >= b[0] && c.bbox[1] <= b[3] && c.bbox[3] >= b[1]) : [];
    const near = close && cs.length > 0 && cs.length <= 9;
    let detail = false, cf = [], sf = [];
    if (near) {
      cf = cs.map(c => want(c.file)).filter(Boolean);
      detail = cf.length === cs.length;
      if (detail && layer === "school") {      // a school district's lines do not follow precincts: its own file, for each district the precincts in view lie in
        const ids = new Set();
        for (const f of cf) for (const g of f.objects.precincts.geometries) { const bb = g.bbox;
          if (bb[0] > b[2] || bb[2] < b[0] || bb[1] > b[3] || bb[3] < b[1]) continue;
          (g.properties.school || []).concat(g.properties.school_edge || []).forEach(i => ids.add(i)); }
        if (ids.size > 40) detail = false;
        else { sf = [...ids].map(i => want(schoolPath(i))).filter(Boolean); if (sf.length < ids.size) detail = false; }
      }
    }
    const lf = detail ? null : (near ? files[L.file] || null : (L.file ? want(L.file) : null));
    return {near, detail, cf, sf, lf, b};
  }

  /* ----- drawing ----- */
  function trace(a, k, ox, oy, shut) {
    ctx.moveTo(a[0] * k + ox, a[1] * k + oy);
    for (let i = 2; i < a.length; i += 2) ctx.lineTo(a[i] * k + ox, a[i + 1] * k + oy);
    if (shut) ctx.closePath();
  }
  function arcs(f, test) {      // a path of the lines of a file that pass the test and can be seen
    const k = scale(), ox = W / 2 - view.x * k, oy = H / 2 - view.y * k, x0 = view.x - W / 2 / k, x1 = view.x + W / 2 / k, y0 = view.y - H / 2 / k, y1 = view.y + H / 2 / k;
    ctx.beginPath();
    for (let a = 0; a < f._w.length; a++) { const b = f._wb[a]; if (b[2] < x0 || b[0] > x1 || b[3] < y0 || b[1] > y1 || (test && !test(a))) continue; trace(f._w[a], k, ox, oy, false); }
  }
  function shapes(list) {      // a path of whole shapes: [[file, shape], ...]
    const k = scale(), ox = W / 2 - view.x * k, oy = H / 2 - view.y * k;
    ctx.beginPath();
    for (const [f, g] of list) for (const a of rings(f, g)) trace(a, k, ox, oy, true);
  }
  function stroke(color, width, dash, under) {
    ctx.lineJoin = "round"; ctx.lineCap = "round"; ctx.setLineDash(dash || []);
    if (under) { ctx.strokeStyle = under; ctx.lineWidth = width + 2.6; ctx.stroke(); }
    ctx.strokeStyle = color; ctx.lineWidth = width; ctx.stroke(); ctx.setLineDash([]);
  }
  function outline(P, kind, id) {      // the path of one shape's outline, from whichever files are in use; false when none has it
    if (P.detail && kind !== "school" && (kind === "county" || KINDS.indexOf(kind) >= 0)) {
      const k = scale(), ox = W / 2 - view.x * k, oy = H / 2 - view.y * k, m = bit(kind);
      ctx.beginPath();
      for (const f of P.cf) { const gs = f.objects.precincts.geometries, S = f.arcSides;
        for (let a = 0; a < f._w.length; a++) { if (!(f.arcMask[a] & m)) continue;
          const r = S[2 * a], l = S[2 * a + 1];
          if ((r >= 0 && holds(gs[r].properties[kind], id)) === (l >= 0 && holds(gs[l].properties[kind], id))) continue;
          trace(f._w[a], k, ox, oy, false); } }
      return true;
    }
    const sf = kind === "school" ? files[schoolPath(id)] : null;
    if (sf) { shapes([[sf, sf.objects.school.geometries[0]]]); return true; }
    const lf = files[(LAYER[kind] || {}).file], g = lf && byId(lf, kind)[id];
    if (g) { shapes([[lf, g]]); return true; }
    return false;
  }
  function body(P, kind, id) {      // the path of one shape's inside
    if (P.detail && kind !== "school" && (kind === "county" || KINDS.indexOf(kind) >= 0)) {
      const list = [];
      for (const f of P.cf) for (const g of f.objects.precincts.geometries) if (holds(g.properties[kind], id)) list.push([f, g]);
      shapes(list); return list.length > 0;
    }
    return outline(P, kind, id);
  }
  const short = (kind, id, name) => opt.short ? opt.short(kind, id, name) : name;
  function labels(P, col) {
    const k = scale(), out = [], b = P.b;
    ctx.font = "600 12px " + (col.sans || "sans-serif"); ctx.textAlign = "center"; ctx.textBaseline = "middle";
    if (P.detail) {
      const acc = {};
      for (const f of P.cf) for (const g of f.objects.precincts.geometries) {
        const c = g.properties.c; if (!c || c[0] < b[0] || c[0] > b[2] || c[1] < b[1] || c[1] > b[3]) continue;
        let v = g.properties[layer]; if (Array.isArray(v)) v = v[0]; if (v == null) continue;
        const e = acc[v] || (acc[v] = {x: 0, y: 0, n: 0}); e.x += X(mx(c[0])); e.y += Y(my(c[1])); e.n++; }
      for (const [id, e] of Object.entries(acc)) { const text = short(layer, id, nameOf(layer, id)); if (text) out.push({x: e.x / e.n, y: e.y / e.n, text, pri: e.n}); }
    } else if (P.lf) {
      for (const g of P.lf.objects[layer].geometries) { const bb = g.bbox, c = g.properties.c;
        if (!c || bb[0] > b[2] || bb[2] < b[0] || bb[1] > b[3] || bb[3] < b[1]) continue;
        const text = short(layer, g.id, g.properties.name); if (!text) continue;
        const w = (mx(bb[2]) - mx(bb[0])) * k, h = (my(bb[1]) - my(bb[3])) * k;
        if (w < ctx.measureText(text).width + 3 || h < 14) continue;
        out.push({x: X(mx(c[0])), y: Y(my(c[1])), text, pri: w * h}); }
    }
    out.sort((a, b2) => b2.pri - a.pri);
    const put = [];
    for (const L of out.slice(0, 400)) { const w = ctx.measureText(L.text).width / 2 + 4;
      if (L.x - w < 0 || L.x + w > W || L.y < 9 || L.y > H - 9) continue;
      if (put.some(p => Math.abs(p.x - L.x) < p.w + w && Math.abs(p.y - L.y) < 16)) continue;
      put.push({x: L.x, y: L.y, w});
      ctx.lineWidth = 3.5; ctx.strokeStyle = col.halo; ctx.lineJoin = "round"; ctx.strokeText(L.text, L.x, L.y);
      ctx.fillStyle = col.ink; ctx.fillText(L.text, L.x, L.y);
      if (put.length >= 70) break; }
  }
  function draw() {
    if (dead || !W || !view) return;
    const cs = getComputedStyle(document.documentElement), V = n => cs.getPropertyValue(n).trim();
    const col = {bg: V("--bg") || "#f4f4f0", surface: V("--surface") || "#fff", ink: V("--ink") || "#111", line: V("--line-strong") || "#bbb",
      accent: V("--accent") || "#0f7a6a", gold: V("--gold") || "#b8860b", sans: V("--sans")};
    col.halo = streets ? "rgba(255,255,255,.92)" : col.surface;
    if (streets) { col.ink = "#14171c"; col.accent = "#0b5d51"; col.gold = "#a36f00"; col.line = "#7d8590"; }      // the street pictures are light in both themes, so over them the lines keep one set of colours
    const P = plan(), under = streets ? "rgba(255,255,255,.85)" : null;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, W, H);
    const st = files[(LAYER.state || {}).file] || (LAYER.state ? want(LAYER.state.file) : null);
    if (!streets) { ctx.fillStyle = col.bg; ctx.fillRect(0, 0, W, H);
      if (st) { shapes(st.objects.state.geometries.map(g => [st, g])); ctx.fillStyle = col.surface; ctx.fill("evenodd"); } }
    const cbit = bit("county");
    if (layer !== "county") {      // the counties, faintly, to say where things are
      if (P.detail && cbit) { for (const f of P.cf) { arcs(f, a => f.arcMask[a] & cbit); stroke(col.line, 1, null, null); } }
      else { const cl = files[(LAYER.county || {}).file] || (LAYER.county ? want(LAYER.county.file) : null); if (cl) { arcs(cl); stroke(col.line, 1, null, null); } }
    }
    const lb = bit(layer);
    if (P.detail && layer === "school") { shapes(P.sf.map(f => [f, f.objects.school.geometries[0]])); stroke(col.accent, 1.8, null, under); }
    else if (P.detail) { for (const f of P.cf) { arcs(f, layer === "county" ? (a => f.arcMask[a] & cbit) : (a => f.arcMask[a] & lb)); stroke(col.accent, 1.8, null, under); } }
    else if (P.lf) { arcs(P.lf); stroke(col.accent, layer === "mcd" && view.z < 8 ? .7 : 1.3, null, under); }
    if (st && !P.detail) { shapes(st.objects.state.geometries.map(g => [st, g])); stroke(col.ink, 1.4, null, null); }      // close in, the state's own edge is among the county lines already drawn
    if (mine) {      // the reader's own: their precinct where its file is here, and their district of the kind being drawn
      const mf = mine.c && COUNTY[mine.c] ? files[COUNTY[mine.c].file] : null, mg = mf && mine.p ? byId(mf, "precincts")[mine.p] : null;
      if (mg && view.z >= 10.5) { shapes([[mf, mg]]); ctx.fillStyle = col.gold; ctx.globalAlpha = .16; ctx.fill("evenodd"); ctx.globalAlpha = 1; stroke(col.gold, 2, null, under); }
      const id = mine.ids && mine.ids[layer];
      if (id && outline(P, layer, id)) stroke(col.gold, 3, [7, 5], under);
      if (mine.at && !pin && (!mg || view.z < 10.5)) { const x = X(mx(mine.at[0])), y = Y(my(mine.at[1]));
        ctx.beginPath(); ctx.arc(x, y, 7, 0, 2 * Math.PI); ctx.fillStyle = col.gold; ctx.globalAlpha = .25; ctx.fill(); ctx.globalAlpha = 1; ctx.lineWidth = 2.5; ctx.strokeStyle = col.gold; ctx.stroke(); }
    }
    if (sel && sel.id != null) {
      if (body(P, sel.kind, sel.id)) { ctx.fillStyle = col.accent; ctx.globalAlpha = .17; ctx.fill("evenodd"); ctx.globalAlpha = 1; }
      if (outline(P, sel.kind, sel.id)) stroke(col.ink, 2.6, null, under);
    }
    if (polls && view.z >= 11.5) for (const p of polls.places) { if (!p.lonlat) continue; const x = X(mx(p.lonlat[0])), y = Y(my(p.lonlat[1])); if (x < -8 || x > W + 8 || y < -8 || y > H + 8) continue;
      ctx.beginPath(); ctx.rect(x - 5, y - 5, 10, 10); ctx.fillStyle = col.ink; ctx.fill(); ctx.lineWidth = 2; ctx.strokeStyle = col.halo; ctx.stroke(); }
    labels(P, col);
    if (keys) { ctx.beginPath(); ctx.moveTo(W / 2 - 9, H / 2); ctx.lineTo(W / 2 + 9, H / 2); ctx.moveTo(W / 2, H / 2 - 9); ctx.lineTo(W / 2, H / 2 + 9); stroke(col.ink, 2, null, "rgba(255,255,255,.9)"); }
    el.classList.toggle("zoomed", view.z > fit.z + .05);
    if (pinEl) { pinEl.hidden = !pin; if (pin) pinEl.style.transform = "translate(" + X(mx(pin[0])).toFixed(1) + "px," + Y(my(pin[1])).toFixed(1) + "px)"; }
    placeTiles();
    if (streets) { clearTimeout(tileTimer); tileTimer = setTimeout(askTiles, 140); }
    if (opt.onView) opt.onView({z: view.z, detail: P.detail, near: P.near, whole: view.z <= fit.z + .01, waiting: Object.keys(waits).length,
      failed: Object.keys(failed).some(p => !files[p] && Date.now() - failed[p] < 60000)});
  }

  /* ----- the street pictures (off until a reader asks): OpenStreetMap's standard tiles, only the squares in view, never ahead of the view ----- */
  function placeTiles() {
    const k = scale();
    for (const [key, im] of tiles) { const p = key.split("/"), u = TILE / Math.pow(2, +p[0]), s = u * k;
      im.style.width = im.style.height = (s + .5).toFixed(2) + "px";
      im.style.transform = "translate(" + X(+p[1] * u).toFixed(2) + "px," + Y(+p[2] * u).toFixed(2) + "px)"; }
  }
  let keepNow = new Set();      // the squares the view wants now; the ones it had stay underneath until these have come
  function sweep() { for (const [key, im] of tiles) if (!keepNow.has(key)) { im.remove(); tiles.delete(key); } }
  function askTiles() {
    if (!streets || dead) return;
    const z = Math.max(0, Math.min(TILEZ, Math.round(view.z))), n = Math.pow(2, z), u = TILE / n, k = scale();
    const x0 = Math.floor((view.x - W / 2 / k) / u), x1 = Math.floor((view.x + W / 2 / k) / u), y0 = Math.floor((view.y - H / 2 / k) / u), y1 = Math.floor((view.y + H / 2 / k) / u);
    const keep = new Set();
    for (let x = x0; x <= x1; x++) for (let y = y0; y <= y1; y++) if (x >= 0 && y >= 0 && x < n && y < n) keep.add(z + "/" + x + "/" + y);
    if (keep.size > 48) return;      // never a flood of requests
    keepNow = keep;
    let asked = 0;
    for (const key of keep) { if (tiles.has(key)) continue;
      const im = new Image(); im.alt = ""; im.draggable = false; im.decoding = "async";
      const done = () => { tilePending = Math.max(0, tilePending - 1); if (!tilePending) sweep(); };
      im.onload = done; im.onerror = () => { im.style.visibility = "hidden"; done(); };
      tilePending++; asked++; tiles.set(key, im); tilesEl.appendChild(im); im.src = TILES + key + ".png"; }
    placeTiles();
    if (!asked && !tilePending) sweep();
    else setTimeout(() => { if (!dead && streets) sweep(); }, 4000);
  }
  function setStreets(on) {
    streets = !!on; el.classList.toggle("streets", streets);
    if (attrEl) attrEl.hidden = !streets;
    if (!streets) { clearTimeout(tileTimer); tilePending = 0; keepNow = new Set(); sweep(); }
    else if (Math.abs(view.z - Math.round(view.z)) > .01 && view.z > fit.z + .01) view.z = Math.round(view.z);
    schedule();
  }

  /* ----- which shape a spot is in ----- */
  function nameOf(kind, id) {
    const lf = files[(LAYER[kind] || {}).file], g = lf && byId(lf, kind)[id];
    if (g) return g.properties.name;
    for (const c of IDX.counties) { const f = files[c.file]; if (f && f.names && f.names[kind] && f.names[kind][id]) return f.names[kind][id]; }
    return opt.nameOf ? opt.nameOf(kind, id) : id;
  }
  function precinctAt(P, lon, lat) {
    for (const f of P.cf) { const bb = f.bbox; if (lon < bb[0] - .01 || lon > bb[2] + .01 || lat < bb[1] - .01 || lat > bb[3] + .01) continue;
      const h = MNGeo.precinctAt(f, lon, lat); if (h && h.inside) return {file: f, geometry: h.geometry, edge: h.edge}; }
    return null;
  }
  function at(px, py) {
    const ll = lonLat(px, py), lon = ll[0], lat = ll[1], P = plan();
    if (polls && view.z >= 11.5) { let best = null, bd = 15;
      for (const p of polls.places) { if (!p.lonlat) continue; const d = Math.hypot(X(mx(p.lonlat[0])) - px, Y(my(p.lonlat[1])) - py); if (d < bd) { bd = d; best = p; } }
      if (best) return {kind: "poll", place: best, lon, lat}; }
    let id = null, precinct = null;
    if (P.detail) {
      const h = precinctAt(P, lon, lat);
      if (h) { precinct = h.geometry; const p = precinct.properties;
        if (layer === "school") { const all = (p.school || []).concat(p.school_edge || []);
          if (all.length === 1 && !p.school_out) id = all[0];
          else for (const i of all) { const sf = files[schoolPath(i)]; if (sf && MNGeo.inside(sf, sf.objects.school.geometries[0], lon, lat)) { id = i; break; } } }
        else { const v = p[layer]; id = Array.isArray(v) ? (v[0] == null ? null : v[0]) : (v == null ? null : v); } }
    } else if (P.lf) { const h = MNGeo.shapeAt(P.lf, layer, lon, lat); if (h) id = h.geometry.id; }
    else return {kind: layer, id: null, loading: true, lon, lat};      // the lines for this view are still on their way
    return {kind: layer, id, name: id == null ? "" : nameOf(layer, id), lon, lat, precinct: precinct ? {id: precinct.id, name: precinct.properties.name} : null};
  }
  function pick(px, py) { const r = at(px, py); if (r.kind !== "poll") { sel = r.id == null ? null : {kind: r.kind, id: r.id}; schedule(); } if (opt.onPick) opt.onPick(r); }
  function locate(lon, lat) {      // the precinct a spot is in, worked out here: the county files whose box holds it, then the reader's own exact test
    const cs = IDX.counties.filter(c => lon >= c.bbox[0] - .003 && lon <= c.bbox[2] + .003 && lat >= c.bbox[1] - .003 && lat <= c.bbox[3] + .003);
    if (!cs.length) return Promise.resolve(null);
    return Promise.all(cs.map(c => load(c.file))).then(fs => {
      const hits = [];
      fs.forEach(f => { const h = MNGeo.precinctAt(f, lon, lat); if (!h) return; [h].concat(h.near || []).forEach(x => hits.push({file: f, geometry: x.geometry, edge: x.edge, inside: !!x.inside})); });
      if (!hits.length) return null;
      hits.sort((a, b) => (b.inside - a.inside) || (a.edge - b.edge));
      const best = hits[0], near = hits.slice(1).filter(x => x.edge <= MNGeo.NEAR && x.geometry !== best.geometry);
      const out = {lon, lat, county: best.file.county, file: best.file, precinct: best.geometry, inside: best.inside, edge: best.edge, near: near.map(x => x.geometry), school: null, schoolKnown: true};
      return new Promise(res => {
        let over = false; const end = id => { if (over) return; over = true; out.school = id; res(out); };
        try { MNGeo.schoolAt(best.geometry, lon, lat, (id, cb) => { load(schoolPath(id)).then(cb).catch(() => { out.schoolKnown = false; end(null); }); }, end); }
        catch (e) { out.schoolKnown = false; end(null); }
      });
    });
  }

  /* ----- one shape, found by its id: the layer, the view fitted to it, and it selected ----- */
  function boxOf(kind, id, counties) {
    if (kind === "county" && COUNTY[id]) return Promise.resolve(COUNTY[id].bbox);
    const lf = files[(LAYER[kind] || {}).file];
    if (lf) { const g = byId(lf, kind)[id]; return Promise.resolve(g ? g.bbox : null); }
    if (kind === "school") return load(schoolPath(id)).then(f => f.bbox, () => null);
    if (counties && counties.length && KINDS.indexOf(kind) >= 0 && counties.every(c => COUNTY[c]))
      return Promise.all(counties.map(c => load(COUNTY[c].file).catch(() => null))).then(fs => { let b = null;
        fs.forEach(f => { if (f) f.objects.precincts.geometries.forEach(g => { if (!holds(g.properties[kind], id)) return; const x = g.bbox;
          b = b ? [Math.min(b[0], x[0]), Math.min(b[1], x[1]), Math.max(b[2], x[2]), Math.max(b[3], x[3])] : x.slice(); }); });
        return b; });
    return LAYER[kind] ? load(LAYER[kind].file).then(f => { const g = byId(f, kind)[id]; return g ? g.bbox : null; }, () => null) : Promise.resolve(null);
  }
  function focus(kind, id, counties) {
    if (LAYER[kind]) layer = kind;
    sel = {kind, id};
    return boxOf(kind, id, counties).then(b => { if (dead) return false; if (b) { const v = fitTo(b, Math.min(48, W / 8), 15.5); if (streets) v.z = Math.floor(v.z); setView(v); } else schedule(); return !!b; });
  }

  /* ----- hands: one finger or the mouse moves the map, two fingers pinch, the wheel and a double tap zoom, the keyboard does all of it ----- */
  const ptr = new Map();
  let drag = null, pinch = null, lastTap = null, wheelSum = 0, wheelAt = 0;
  const local = e => { const r = el.getBoundingClientRect(); return [e.clientX - r.left, e.clientY - r.top]; };
  el.addEventListener("pointerdown", e => {
    if (e.button || e.target.closest("a, button")) return;      // the credit keeps its click
    lastType = e.pointerType || "";
    if (keys) { keys = false; schedule(); }
    if (e.isPrimary && ptr.size) { ptr.clear(); pinch = null; }      // a first finger while one is still counted: its lift was missed, so start afresh
    ptr.set(e.pointerId, local(e));
    if (ptr.size === 1) drag = {x: e.clientX, y: e.clientY, vx: view.x, vy: view.y, moved: false, touch: e.pointerType === "touch"};
    else if (ptr.size === 2) { const p = [...ptr.values()], cx = (p[0][0] + p[1][0]) / 2, cy = (p[0][1] + p[1][1]) / 2, k = scale();
      pinch = {d: Math.hypot(p[0][0] - p[1][0], p[0][1] - p[1][1]) || 1, z: view.z, wx: view.x + (cx - W / 2) / k, wy: view.y + (cy - H / 2) / k}; drag = null; }
  });
  addEventListener("pointermove", e => {
    if (!ptr.has(e.pointerId)) return;
    ptr.set(e.pointerId, local(e));
    if (pinch && ptr.size >= 2) { const p = [...ptr.values()], cx = (p[0][0] + p[1][0]) / 2, cy = (p[0][1] + p[1][1]) / 2;
      const z = Math.max(fit.z, Math.min(MAXZ, pinch.z + Math.log2((Math.hypot(p[0][0] - p[1][0], p[0][1] - p[1][1]) || 1) / pinch.d))), k = Math.pow(2, z);
      view = clamp({x: pinch.wx - (cx - W / 2) / k, y: pinch.wy - (cy - H / 2) / k, z}); schedule(); return; }
    if (!drag) return;
    const dx = e.clientX - drag.x, dy = e.clientY - drag.y;
    if (!drag.moved && Math.hypot(dx, dy) < 5) return;
    drag.moved = true; el.classList.add("drag");
    const k = scale(); view = clamp({x: drag.vx - dx / k, y: drag.vy - dy / k, z: view.z}); schedule();
  }, sig);
  function lift(e) {
    if (!ptr.has(e.pointerId)) return;
    ptr.delete(e.pointerId);
    if (pinch) { if (ptr.size < 2) { pinch = null; if (streets) { view.z = Math.max(fit.z, Math.round(view.z)); view = clamp(view); } schedule(); } return; }
    const d = drag; drag = null; el.classList.remove("drag");
    if (!d || d.moved || e.type !== "pointerup") return;
    const p = local(e), now = Date.now();
    if (d.touch && lastTap && now - lastTap.t < 330 && Math.hypot(p[0] - lastTap.x, p[1] - lastTap.y) < 32) { lastTap = null; stepIn(p[0], p[1]); return; }      // a double tap
    lastTap = {t: now, x: p[0], y: p[1]};
    pick(p[0], p[1]);
  }
  addEventListener("pointerup", lift, sig);
  addEventListener("pointercancel", lift, sig);
  el.addEventListener("dblclick", e => { if (e.target.closest("a, button")) return; e.preventDefault(); if (lastType === "touch") return; const p = local(e); stepIn(p[0], p[1]); });
  let pageScroll = 0;
  addEventListener("scroll", () => { pageScroll = Date.now(); }, {passive: true, signal: off.signal});
  el.addEventListener("wheel", e => {
    const out = e.deltaY > 0;
    if (Date.now() - pageScroll < 400) return;      // a reader rolling the page past the map is not asking the map to zoom
    if ((out && view.z <= fit.z + 1e-6) || (!out && view.z >= MAXZ - 1e-6)) return;      // nothing left to zoom: the page scrolls on
    e.preventDefault();
    wheelSum += e.deltaY * (e.deltaMode === 1 ? 33 : 1) * (e.ctrlKey ? 5 : 1);
    const now = Date.now();
    if (Math.abs(wheelSum) < 50 || now - wheelAt < 120) return;      // a notch of the wheel is one step; a trackpad's small pushes add up to one
    wheelAt = now; const p = local(e), into = wheelSum < 0; wheelSum = 0;
    if (into) stepIn(p[0], p[1]); else stepOut(p[0], p[1]);
  }, {passive: false});
  el.addEventListener("keydown", e => {
    if (e.target !== el || e.ctrlKey || e.metaKey || e.altKey) return;
    const s = 90 / scale(), k = e.key; let used = true;
    if (k === "ArrowLeft") setView({x: view.x - s, y: view.y, z: view.z}); else if (k === "ArrowRight") setView({x: view.x + s, y: view.y, z: view.z});
    else if (k === "ArrowUp") setView({x: view.x, y: view.y - s, z: view.z}); else if (k === "ArrowDown") setView({x: view.x, y: view.y + s, z: view.z});
    else if (k === "+" || k === "=") stepIn(); else if (k === "-" || k === "_") stepOut(); else if (k === "0") setView(fit);
    else if (k === "Enter" || k === " ") pick(W / 2, H / 2); else if (k === "Escape") { sel = null; schedule(); if (opt.onPick) opt.onPick({kind: layer, id: null, cleared: true}); }
    else used = false;
    if (used) { e.preventDefault(); if (!keys) { keys = true; schedule(); } }
  });
  el.addEventListener("blur", () => { if (keys) { keys = false; schedule(); } });
  addEventListener("resize", resize, sig);
  const ro = typeof ResizeObserver === "function" ? new ResizeObserver(resize) : null; if (ro) ro.observe(el);
  const mo = new MutationObserver(schedule); mo.observe(document.documentElement, {attributes: true, attributeFilter: ["data-theme"]});
  resize();
  if (!W) setTimeout(resize, 120);

  return {
    layer: () => layer, view: () => view && {z: view.z, lon: lonAt(view.x), lat: latAt(view.y)}, nameOf, locate, focus, load,
    setLayer(kind) { if (LAYER[kind] && kind !== layer) { layer = kind; if (sel && sel.kind !== kind) sel = null; schedule(); } },
    select(kind, id) { sel = id == null ? null : {kind, id}; schedule(); },
    setMine(m) { mine = m || null; if (mine && mine.c && COUNTY[mine.c] && view && view.z >= 10.5) want(COUNTY[mine.c].file); schedule(); },
    setPin(ll) { pin = ll || null; schedule(); },
    setPolls(doc) { polls = doc && doc.places ? doc : null; schedule(); },
    setStreets, streets: () => streets,
    zoomIn: () => stepIn(), zoomOut: () => stepOut(), whole: () => setView(fit),
    goTo(lon, lat, z) { setView({x: mx(lon), y: my(lat), z: z == null ? view.z : z}); },
    fitBox(b, most, least) { const v = fitTo(b, Math.min(60, W / 6), most); if (streets) v.z = Math.floor(v.z); if (least && v.z < least) v.z = least; setView(v); },
    pickAt(lon, lat) { pick(X(mx(lon)), Y(my(lat))); },
    entries(kind) { const f = files[(LAYER[kind] || {}).file]; return f ? f.objects[kind].geometries.map(g => [g.id, g.properties.name]) : null; },
    props(kind, id) { const f = files[(LAYER[kind] || {}).file], g = f && byId(f, kind)[id]; return g ? g.properties : null; },
    redraw: schedule, resize,
    destroy() { dead = true; off.abort(); if (ro) ro.disconnect(); mo.disconnect(); clearTimeout(tileTimer); keepNow = new Set(); sweep(); }
  };
}
window.BallotMap = BallotMap;
})();

/* ---------- the map set into the page's "your ballot": the switch for which lines to draw, the panel beside it, the pin, the
   notices that travel with the lines. It uses the page's own words and helpers by name (ST, D, raceTitle, legPreview ...). ---------- */
window.GEOKIT = (function () {
  const G = BOOT.geo;
  let map = null, IDX = null, POLLS = null, spot = null, box = null, ready = null, wanted = null, listed = "";
  /* the map files' own words and ids, where they are not the page's usual ones: what a kind of district is called there (GW), what its
     places' names say they are (GM), and a county's id in the files against the key the page files it under (pk, gk) */
  const GW = G.words || {}, GM = G.muni && G.muni.length ? G.muni : (ST.muni && ST.muni.length ? ST.muni : ["city"]), CK = G.ck || {}, KC = {};
  Object.keys(CK).forEach(k => { KC[CK[k]] = k; });
  const pk = id => CK[id] || id, gk = id => KC[id] || id;
  const bare = w => String(w).replace(/^county\s+/i, ""), title = w => String(w).replace(/\b[a-z]/g, c => c.toUpperCase());
  const said = (kind, usual) => GW[kind] ? [capital(bare(GW[kind])) + "s", capital(GW[kind])] : usual;
  const KW = {county: [capital(COS), capital(CO1)], mcd: [capital(andList(GM.map(w => MUNIS[w] || w))), capital(orList(GM))],
    school: [capital(ST.schoolOne || "school district") + "s", capital(ST.schoolOne || "school district")], com: said("com", ["Commissioner districts", "County commissioner district"]),
    ward: said("ward", ["Wards", "City ward"]), house: [ST.loT, ST.loD], senate: [ST.upT, ST.upD], cd: ["Congress", "Congressional district"], judicial: said("judicial", ["Judicial districts", "Judicial district"]),
    swcd: ["Soil and water", "Soil and water district"], hospital: ["Hospital districts", "Hospital district"], park: ["Park districts", "Park district"]};
  const ORDER = ["county", "mcd", "school", "com", "ward", "house", "senate", "cd", "judicial", "swcd", "hospital", "park"];
  const kinds = () => ORDER.filter(k => G.kinds.includes(k)).concat(G.kinds.filter(k => !ORDER.includes(k)));
  const words = k => KW[k] || [capital(k), capital(k)];
  const side = html => { const s = $("#gside"); if (s) s.innerHTML = html; };
  const feet = m => { const f = m * 3.2808; return f < 20 ? Math.max(5, Math.round(f / 5) * 5) : Math.round(f / 10) * 10; };
  const schoolWho = () => { const s = ((IDX && IDX.sources) || []).find(x => /school/i.test((x.id || "") + " " + (x.title || ""))); return s ? String(s.agency || "").split(/[;,]/)[0].trim() : "the state's school district map"; };
  const finder = () => { const P = G.polls || {}; return P.finder ? `<a href="${esc(P.finder)}" target="_blank" rel="noopener">Open the ${WHO} polling place finder</a>` : ""; };

  /* what a shape is called, from what the page already holds (the map's own files say it first, where they are here) */
  function dataName(kind, id) {
    const s = String(id), a = s.split("|")[0], b = s.split("|")[1];
    if (kind === "county") return cName(pk(s));
    if (kind === "mcd") return (D.places.M[mKey(s)] || {}).n || s;
    if (kind === "school") return SCHG[s] ? placeName(SCHG[s]) : s;
    if (kind === "house") return `${ST.loD} ${s}`;
    if (kind === "senate") return `${ST.upD} ${s}`;
    if (kind === "cd") return `Congressional District ${s}`;
    if (kind === "judicial") return GW.judicial ? `${capital(GW.judicial)} ${s.replace(/^\D+/, "")}` : judicialName(s.replace(/^\D+/, ""));
    if (kind === "com") return `${cName(pk(a))}, ${GW.com ? title(bare(GW.com)) : "Commissioner District"} ${b}`;
    if (kind === "ward") return `${(D.places.M[a] || {}).n || a}, ${b}`;
    if (kind === "hospital") return ((D.places.H || {})[s] || {}).n || s;
    const r = (BYG[kind + ":" + s] || [])[0];
    return r ? raceWhere(r) : s;
  }
  function short(kind, id, name) {      // what is written on the map itself
    const s = String(id), n = String(name || "");
    if (kind === "county") return n.replace(/ County$/, "");
    if (kind === "mcd") return n.replace(/ city$/i, "");
    if (kind === "house" || kind === "senate" || kind === "cd") return s;
    if (kind === "judicial") return s.replace(/^\D+/, "");
    if (kind === "com" || kind === "park") return s.split("|")[1] || s;
    if (kind === "ward") return s.split("|")[1] || s;
    if (kind === "school") return n.replace(/\s*\([^)]*\)\s*$/, "").replace(/\s+(?:Public\s+)?School\s+Districts?$/i, "");
    return n;
  }
  function racesOf(kind, id) { return kind === "mcd" ? D.races.filter(r => r.pk === mPk(id) && LOCAL.includes(r.lv)) : (BYG[kind + ":" + id] || []); }
  function countiesOf(kind, id) {      // the counties whose precinct files hold a shape, so its lines can be found without the layer's whole file
    const s = String(id), a = s.split("|")[0];
    if (kind === "mcd") return (D.places.M[s] || {}).c || [];
    if (kind === "ward") return (D.places.M[a] || {}).c || [];
    if (kind === "com") return [a];
    if (kind === "park") return D.counties[a] ? [a] : (D.places.M[a] || {}).c || [];
    if (kind === "hospital") return ((D.places.H || {})[s] || {}).c || [];
    return [...new Set((BYG[kind + ":" + s] || []).flatMap(r => r.c || []))];
  }

  /* ----- the panel beside the map ----- */
  const BACK = () => `<p class="sidehint"><button type="button" class="linkbtn" data-side="home">${MINE && MINE.z ? "Back to where you are" : "Back to the map&rsquo;s key"}</button></p>`;
  function pollHTML(z) {
    const P = G.polls || {};
    if (P.status === "loaded" && POLLS) {
      const i = POLLS.precinct[z.p], pl = i == null ? null : POLLS.places[i], mail = (POLLS.no_place || {})[z.p];
      const tail = `<small>From the ${esc(P.source || "state's list of polling places")}. ${finder() ? `The finder is the authority: ${finder()}.` : ""}</small>`;
      if (pl) return `<div class="gpoll"><b>Your polling place</b>${esc(pl.name)}${pl.address ? `, ${esc(pl.address)}` : ""}${pl.city ? `, ${esc(pl.city)}` : ""}${tail}</div>`;
      return `<div class="gpoll"><b>Your polling place</b>${mail ? `Your ${UNIT} ${esc(mail)}.` : `This ${UNIT} is not on the list of polling places loaded here.`}${tail}</div>`;
    }
    return `<div class="gpoll"><b>Polling places are not shown here</b>${esc(P.why || `No list of polling places is loaded for ${ST.name}.`)}${finder() ? ` ${finder()}.` : ""}</div>`;
  }
  function zonesHTML(z) {      // every district a located reader is in, by name; a tap shows it on the map
    const row = (label, value, kind, id) => value ? `<div><dt>${label}</dt><dd>${kind ? `<button type="button" class="zbtn" data-zone="${esc(kind + ":" + id)}" title="Show it on the map">${esc(value)}</button>` : esc(value)}</dd></div>` : "";
    const nb = z.sch.length - (z.ov || 0), split = nb > 1;      // the districts that share the precinct out; any after them lie over those (a union high school district)
    // whole-number shares that add to 100 when the districts cover the precinct (largest remainders get the spare points);
    // where part of the precinct lies in no district the shares fall short of 100, and are only rounded
    const shares = (() => { const p = (z.pct || []).slice(0, nb).map(Number), sum = p.reduce((a, b) => a + b, 0), out = p.map(Math.floor);
      if (!p.length || p.some(isNaN) || Math.abs(sum - 100) > .6) return p.map(Math.round);
      let spare = 100 - out.reduce((a, b) => a + b, 0);
      p.map((v, i) => [v - out[i], i]).sort((a, b) => b[0] - a[0] || a[1] - b[1]).forEach(([, i]) => { if (spare > 0) { out[i]++; spare--; } });
      return out; })();
    const rows =[row(esc(capital(UNIT)), z.pn), row(esc(capital(CO1)), cName(z.c), "county", z.c), row(esc(KW.mcd[1]), z.mn || dataName("mcd", z.m), "mcd", z.m),
      ...(z.w || []).map(w => row(GW.ward ? esc(capital(GW.ward)) : "City council", w.split("|")[1] || w, "ward", w)),
      z.com ? row(GW.com ? esc(capital(GW.com)) : "County commissioner", "District " + (z.com.split("|")[1] || z.com), "com", z.com) : "",
      ...z.sch.map((i, n) => row(n ? "" : esc(capital(ST.schoolOne || "school district")), ((z.schn || {})[i] || dataName("school", i)) + (n >= nb ? ` (it lies over the other${nb > 1 ? "s" : ""}: you are in it as well)` : split && (z.pct || [])[n] ? ` (about ${shares[n] || "under 1"}% of the ${UNIT}’s area${i === z.s1 ? "; your spot" : ""})` : ""), "school", i)),
      row(esc(ST.loT), z.hd ? "District " + z.hd : "", "house", z.hd), row(esc(ST.upT), z.sd ? "District " + z.sd : "", "senate", z.sd), row("Congress", z.cd ? "District " + z.cd : "", "cd", z.cd),
      row(esc(KW.judicial[1]), z.jd ? dataName("judicial", z.jd) : "", "judicial", z.jd), row("Soil and water", z.sw ? (z.swn || dataName("swcd", z.sw)) : "", "swcd", z.sw),
      row("Hospital district", z.ho ? (z.hon || dataName("hospital", z.ho)) : "", "hospital", z.ho), row("Park district", z.pk ? (z.pkn || dataName("park", z.pk)) : "", "park", z.pk)].join("");
    const edge = !z.in ? `Your spot is on a ${UNIT} line, as near as this map can tell. ${esc(z.pn)} is the nearest ${UNIT}${z.nb ? `; ${esc(z.nb)} is on the other side` : ""}.`
      : z.edge <= 30 ? `Your spot is about ${feet(z.edge)} feet from this ${UNIT}&rsquo;s line${z.nb ? ` with ${esc(z.nb)}` : ""}; a spot that close can fall on either side of it.` : "";
    const acc = z.acc && z.acc > Math.max(40, z.edge) ? `Your device placed you to within about ${num(feet(z.acc))} feet, and the nearest ${UNIT} line is about ${num(feet(z.edge))} feet away, so the ${UNIT} could be a neighbouring one.` : "";
    const school = split ? `Your ${UNIT} is split between ${num(nb)} ${esc(ST.schoolOne || "school district")}s. ${z.s1 ? `By the ${esc(schoolWho())}&rsquo;s map your spot is in ${esc((z.schn || {})[z.s1] || z.s1)}` : "Which one your spot is in could not be settled here"}; ${nb === 2 ? "both are" : "all are"} on the list below, because those lines are generalised.`
      : z.out ? `Part of this ${UNIT} lies in no ${esc(ST.schoolOne || "school district")}.` : "";
    return `<span class="kick">Where you are</span><h3>${esc(z.pn)}</h3>
      <p class="held">Your ${UNIT} and every district it is in, worked out on this device. Tap a name to see it on the map.</p>
      <dl class="zlist">${rows}</dl>
      ${[edge, acc, school].filter(Boolean).map(t => `<p class="znote">${t}</p>`).join("")}
      ${pollHTML(z)}
      <p class="sidehint">${spot ? `The pin is your spot. The exact spot is used here and now and is not kept: after a reload your ${UNIT} stays marked in gold instead. A copy rounded to about half a mile stays on this device, for the site&rsquo;s other pages, until you tap &ldquo;Forget&rdquo;.` : `Your ${UNIT} is marked in gold. The exact spot was not kept; a copy rounded to about half a mile stays on this device until you tap &ldquo;Forget&rdquo;.`} &ldquo;Show streets&rdquo; draws the streets around it; OpenStreetMap&rsquo;s servers then see which map squares are asked for. <button type="button" class="linkbtn" data-zone="me">Go to my ${UNIT}</button></p>`;
  }
  function sideHome() {
    if (MINE && MINE.z) return zonesHTML(MINE.z);
    const k = map ? map.layer() : "county", P = G.polls || {};
    return `<span class="kick">${NM} &middot; the map</span><h3>${esc(words(k)[0])}</h3>
      <p class="held">Tap a place on the map to see its name and open its races. The switch above the map draws other lines; zoom in and the lines become each ${UNIT}&rsquo;s own, down to a street.</p>
      <p class="held"><b>Use my location</b> drops a pin at your spot, finds your ${UNIT} on this device and lists every district you are in.</p>
      ${P.status === "loaded" ? `<p class="held">Polling places appear as small squares once you zoom in.</p>` : `<div class="gpoll"><b>Polling places are not on this map</b>${esc(P.why || `No list of polling places is loaded for ${ST.name}.`)}${finder() ? ` ${finder()}.` : ""}</div>`}`;
  }
  function raceList(rs, more) {
    const top = rs.slice(0, 12), rest = rs.length - top.length;
    return `<ul class="glist">${top.map(r => { const g = general(r); return `<li><a href="${hrefRace(r)}"><b>${esc(raceTitle(r))}${r.sp ? '<span class="tagsp">Special</span>' : ""}</b><span>${g.length ? plural(g.length, "candidate") : (EMPTY || "no candidate on the list")}</span></a></li>`; }).join("")}</ul>${rest > 0 ? `<p class="sidehint">And ${num(rest)} more${more ? `: ${more}` : ""}.</p>` : ""}`;
  }
  function sideShape(kind, id, name, precinct) {
    const rs = racesOf(kind, id), kw = words(kind)[1], at = precinct ? `<p class="sidehint">The ${UNIT} at that spot: ${esc(precinct.name)}.</p>` : "";
    if (kind === "house" || kind === "senate") { const r = legRace(kind === "senate" ? "upper" : "lower", String(id));
      return (r ? legPreview(r) : `<span class="kick">${esc(kw)}</span><h3>${esc(name)}</h3><p class="held">No race for this district is on the ${WHO} list for November 3.</p>`) + at + BACK(); }
    let body;
    if (kind === "cd") { const p = (map && map.props("cd", id)) || {}, rid = p.race || `2026-${ST.code}-H${String(id).padStart(2, "0")}`;
      body = BOOT.links.us ? `<p class="held">The race for the U.S. House here is on the Congress pages.</p><a class="rpgo" href="../us/#race=${encodeURIComponent(rid)}">Open the race &rsaquo;</a>` : `<p class="held">The race for the U.S. House here is not on this page.</p>`; }
    else if (kind === "county") body = `<p class="held">${plural(COUNTS[pk(id)] || 0, "contest")} on the November 3 ballot reach${(COUNTS[pk(id)] || 0) === 1 ? "es" : ""} ${esc(name)}.${rs.length ? " The offices the whole county elects:" : ""}</p>${rs.length ? raceList(rs) : ""}<a class="rpgo" href="#county=${esc(pk(id))}">Open ${esc(name)} &rsaquo;</a>`;
    else if (kind === "judicial") body = rs.length ? raceList(rs, `<a href="#courts">see every district court race</a>`) : `<p class="held">No seat of this district&rsquo;s court is on the ${WHO} list for November 3.</p>`;
    else { const cs = kind === "mcd" ? ((D.places.M[mKey(id)] || {}).c || []) : [];
      body = (rs.length ? raceList(rs) : `<p class="held">No contest for ${esc(name)} is on the ${LWHO} list for November 3.</p>`)
        + (cs.length ? `<p class="sidehint">Everything else on a ballot here: ${cs.map(f => `<a href="#county=${esc(f)}">${esc(cName(f))}</a>`).join(", ")}.</p>` : ""); }
    return `<span class="kick">${esc(kw)}</span><h3>${esc(name)}</h3>${body}${at}${BACK()}`;
  }
  function picked(r) {
    if (r.cleared) { side(sideHome()); return; }
    if (r.kind === "poll") { const p = r.place; side(`<span class="kick">Polling place</span><h3>${esc(p.name)}</h3><p class="held">${esc([p.address, p.city].filter(Boolean).join(", "))}</p><p class="sidehint">${finder() ? `Which ${UNIT}s vote here, and whether yours does, is for the finder to say: ${finder()}.` : ""}</p>${BACK()}`); return; }
    if (r.loading) side(`<span class="kick">${esc(words(r.kind)[1])}</span><p class="held">The lines for this part of the map are still loading. Tap again in a moment.</p>${BACK()}`);
    else if (r.id == null) side(`<span class="kick">${esc(words(r.kind)[1])}</span><p class="held">${r.precinct ? `No ${esc(words(r.kind)[1].toLowerCase())} at that spot (${UNIT} ${esc(r.precinct.name)}).` : `Nothing of ${NM}&rsquo;s is at that spot on the map.`}</p>${BACK()}`);
    else side(sideShape(r.kind, r.id, r.name, r.precinct));
    const s = $("#gside"); if (s && !matchMedia("(hover: hover)").matches && s.getBoundingClientRect().top > innerHeight - 90) s.scrollIntoView({block: "nearest", behavior: calm() ? "auto" : "smooth"});
  }

  /* ----- the switch, the Find box, the notices ----- */
  function findEntries(kind) {      // [[what a reader types, the shape's id]]
    const out = [];
    if (kind === "county") Object.keys(D.counties).forEach(f => out.push([cName(f), gk(f)]));
    else if (kind === "mcd") Object.entries(D.places.M || {}).forEach(([k, P]) => out.push([`${P.n}${(P.c || []).length ? ` (${P.c.map(cShort).join(", ")})` : ""}`, k]));
    else if (kind === "school") Object.entries(D.places.S || {}).forEach(([k, P]) => out.push([P.n, P.g || k]));
    else if (kind === "house") D.hds.forEach(d => out.push([`${ST.loD} ${d}`, d]));
    else if (kind === "senate") D.sds.forEach(d => out.push([`${ST.upD} ${d}`, d]));
    else { const got = map && map.entries(kind);
      if (got) got.forEach(([id, name]) => out.push([name, id]));
      else Object.keys(BYG).filter(k => k.startsWith(kind + ":")).forEach(k => out.push([dataName(kind, k.slice(kind.length + 1)), k.slice(kind.length + 1)])); }
    return out.sort((a, b) => a[0].localeCompare(b[0], undefined, {numeric: true}));
  }
  let found = [];
  function fillFind(force) {
    const inp = $("#gfind"), dl = $("#gfindlist"); if (!inp || !dl || !map) return;
    const k = map.layer(); if (listed === k && !force) return;
    listed = k; found = findEntries(k);
    dl.innerHTML = found.map(([label]) => `<option value="${esc(label)}"></option>`).join("");
  }
  function setLayer(kind, quiet) {
    if (!map) return;
    map.setLayer(kind);
    $$("#glayers button").forEach(b => b.setAttribute("aria-pressed", String(b.dataset.k === kind)));
    const sel = $("#glayer"); if (sel) sel.value = kind;
    const inp = $("#gfind"); if (inp) { inp.value = ""; inp.placeholder = `Find a${/^[aeiou]/i.test(words(kind)[1]) ? "n" : ""} ${words(kind)[1].toLowerCase()}`; inp.setAttribute("aria-label", inp.placeholder + " by name"); }
    listed = "";
    $("#gmap").setAttribute("aria-label", `Map of ${ST.name}: ${words(kind)[0].toLowerCase()}`);
    if (!quiet) side(sideHome());
  }
  function show(kind, id) {      // one shape, by its id: on the map and in the panel (with no id: that kind of line, drawn)
    if (!map) { wanted = [kind, id]; return; }
    if (id == null || id === "") { if (G.kinds.includes(kind)) setLayer(kind); return; }
    if (kind === "county") id = gk(id);      // the page names a county by its own key; the map's files by theirs
    setLayer(kind, true);
    const name = map.nameOf(kind, id);
    side(sideShape(kind, id, name, null));
    map.focus(kind, id, countiesOf(kind, id).map(gk)).then(ok => { if (!map || !$("#gside")) return;      // the page moved on while the lines were fetched
      if (!ok) side(`<span class="kick">${esc(words(kind)[1])}</span><h3>${esc(name)}</h3><p class="held">The map files hold no lines for it, so it cannot be drawn.</p>${racesOf(kind, id).length ? raceList(racesOf(kind, id)) : ""}${BACK()}`);
      else side(sideShape(kind, id, map.nameOf(kind, id), null)); }, () => {});
  }
  function aboutHTML() {
    const N = IDX.notes || {};
    const src = (IDX.sources || []).map(s => `<div class="srcitem"><b>${esc(s.agency || "Source")}</b>: ${esc(s.title || "")}${s.about ? `<small>${esc(s.about)}</small>` : ""}<small><span class="tag fact">Fact</span>${s.url ? ` <a href="${esc(s.url)}" target="_blank" rel="noopener">${esc(hostOf(s.url))}</a>` : ""}${s.published ? ` &middot; published ${esc(s.published)}` : ""}${s.current_to ? ` &middot; current to ${esc(s.current_to)}` : ""}${s.fetched ? ` &middot; read ${esc(s.fetched)}` : ""}${s.rows ? ` &middot; ${num(s.rows)} rows` : ""}${s.sha256 ? ` &middot; SHA-256 ${esc(String(s.sha256).slice(0, 16))}&hellip;` : ""}</small>${s.use ? `<small><b>Its notice on use:</b> ${esc(s.use)}</small>` : ""}${s.disclaimer ? `<small><b>Its disclaimer, word for word:</b> ${esc(s.disclaimer)}</small>` : ""}</div>`).join("");
    const plainly = t => String(t).replace(/\bschool_pct is\b/, "the share shown beside a district is");      // the files' own note names a field; a reader is told what it is
    const notes = Object.keys(N).filter(k => !["disclaimers", "precinct_ids"].includes(k)).map(k => N[k]);      // every note the files carry about their lines; the sources' own disclaimers are shown with the sources below
    return `${notes.filter(t => t && typeof t === "string").map(t => `<p class="ynote">${esc(plainly(t))}</p>`).join("")}<div class="srclist" style="margin-top:12px">${src}</div>`;
  }
  const mineOf = z => ({c: z.gc || z.c, p: z.p, at: z.at, ids: {county: z.gc || z.c, mcd: z.m, ward: (z.w || [])[0], com: z.com, house: z.hd, senate: z.sd, cd: z.cd, judicial: z.jd, swcd: z.sw, hospital: z.ho, park: z.pk, school: z.s1 || z.sch[0]}});
  function zonesOf(r, acc) {      // what is kept of a located reader, on their device only: the precinct and its districts, each with its name; never the spot
    const p = r.precinct.properties, n = r.file.names || {}, nm = (k, id) => (id && (n[k] || {})[id]) || "";
    const sch = (p.school || []).slice(); if (r.school && !sch.includes(r.school)) sch.unshift(r.school);
    // districts that lie over others (a union high school district over the elementary ones that feed it) come last in the list, and
    // with them the shares pass 100: the first ones, up to 100, share the precinct out; the rest lie over those
    const pcts = (p.school || []).length === sch.length ? (p.school_pct || []).map(Number) : []; let nb = 0, sum = 0;
    while (nb < pcts.length && sum + pcts[nb] <= 101.5) sum += pcts[nb++];
    const over = pcts.length === sch.length && nb > 0 && nb < sch.length ? {ov: sch.length - nb} : {};
    return {p: r.precinct.id, pn: p.name, at: p.c, c: pk(p.county), ...(pk(p.county) !== p.county ? {gc: p.county} : {}), ...over, m: p.mcd, mn: nm("mcd", p.mcd), w: p.ward || [], com: p.com || "", hd: p.house || "", sd: p.senate || "", cd: p.cd || "", jd: p.judicial || "",
      sw: p.swcd || "", swn: nm("swcd", p.swcd), ho: p.hospital || "", hon: nm("hospital", p.hospital), pk: p.park || "", pkn: nm("park", p.park),
      sch, schn: Object.fromEntries(sch.map(i => [i, nm("school", i)])), s1: r.school || "", pct: (p.school || []).length === sch.length ? (p.school_pct || []) : [], out: p.school_out || 0,
      edge: Math.round(r.edge), in: r.inside ? 1 : 0, nb: r.near.length ? r.near[0].properties.name : "", acc: Math.round(acc || 0)};
  }
  function locate(lon, lat, acc) {      // a reader's spot, used here and now: the pin, the precinct, every district. The spot itself is never kept.
    return (ready || mount()).then(() => map.locate(lon, lat)).then(r => {
      if (!r) return null;
      const z = zonesOf(r, acc);
      spot = [lon, lat]; box = r.precinct.bbox;
      map.setMine(mineOf(z)); map.select(null); map.setPin(spot);
      map.fitBox([Math.min(box[0], lon), Math.min(box[1], lat), Math.max(box[2], lon), Math.max(box[3], lat)], 15, 11);      // the whole precinct, with the pin in it
      const pin = $("#gmap .gpin"); if (pin) { pin.classList.remove("drop"); void pin.offsetWidth; pin.classList.add("drop"); }
      return z;
    });
  }
  function toMine() {      // the view on a located reader's precinct: around the pin while the spot is known, else around the precinct's own middle
    const z = MINE && MINE.z; if (!z || !map) return;
    if (spot && box) map.fitBox([Math.min(box[0], spot[0]), Math.min(box[1], spot[1]), Math.max(box[2], spot[0]), Math.max(box[3], spot[1])], 15, 11);
    else if (z.at) map.goTo(z.at[0], z.at[1], 13);
  }
  function rough(lon, lat) {      // a rounded spot (about half a mile): good for the county and the legislative districts, not for a precinct
    return (ready || mount()).then(() => map.locate(lon, lat)).then(r => r ? {c: pk(r.precinct.properties.county), hd: r.precinct.properties.house || "", sd: r.precinct.properties.senate || ""} : null);
  }
  function mount() {
    const root = $("#gmapsec");
    if (!root) return Promise.reject(new Error("no map on this page"));
    if (map) { map.destroy(); map = null; }
    listed = "";
    const get = IDX ? Promise.resolve(IDX) : fetch(G.base + "index.json?v=" + G.v).then(r => r.ok ? r.json() : Promise.reject(new Error(String(r.status))));
    ready = get.then(idx => {
      IDX = idx;
      if (!root.isConnected) throw new Error("the page moved on");
      const ks = kinds();
      $("#glayers").innerHTML = ks.map(k => `<button type="button" data-k="${k}" aria-pressed="${k === "county"}">${esc(words(k)[0])}</button>`).join("");
      $("#glayer").innerHTML = ks.map(k => `<option value="${k}">${esc(words(k)[0])}</option>`).join("");
      map = BallotMap($("#gmap"), {index: idx, base: G.base, v: G.v, layer: "county", nameOf: dataName, short, onPick: picked,
        onView: v => { const n = $("#gline"); if (n) n.textContent = v.failed && !v.detail ? "Some of the map’s lines could not be loaded. Check your connection; the map asks again as you move it." : v.detail ? `Here the lines are each ${UNIT}’s own.` : v.near ? `Loading this area’s ${UNIT} lines…` : `Far out the lines are simplified; zoom in and each ${UNIT}’s own lines take over.`;
          const me = $("#gme"); if (me) me.hidden = !(MINE && MINE.z); }});
      $("#gabout .fbody").innerHTML = aboutHTML();
      setLayer("county", true);
      if (MINE && MINE.z) { map.setMine(mineOf(MINE.z)); if (spot) map.setPin(spot); toMine(); }      // a reader found before: the map opens on their precinct
      side(sideHome());
      if ((G.polls || {}).status === "loaded" && !POLLS) fetch(G.base + G.polls.file + "?v=" + G.v).then(r => r.ok ? r.json() : null).then(d => { if (d) { POLLS = d; if (map) map.setPolls(d); if ($("#gside") && MINE && MINE.z) side(sideHome()); } }, () => {});
      else if (POLLS) map.setPolls(POLLS);
      if (wanted) { const w = wanted; wanted = null; show(w[0], w[1]); }
    });
    root.addEventListener("click", e => {
      const b = e.target.closest("button, a"); if (!b || !map) return;
      if (b.dataset.k) setLayer(b.dataset.k);
      else if (b.dataset.z === "in") map.zoomIn(); else if (b.dataset.z === "out") map.zoomOut(); else if (b.dataset.z === "fit") map.whole();
      else if (b.dataset.z === "me" || b.dataset.zone === "me") { if (MINE && MINE.z) { toMine(); $("#gmap").scrollIntoView({block: "nearest"}); } }
      else if (b.dataset.zone) { const i = b.dataset.zone.indexOf(":"); show(b.dataset.zone.slice(0, i), b.dataset.zone.slice(i + 1)); }
      else if (b.dataset.side === "home") { map.select(null); side(sideHome()); }
      else if (b.id === "gstreets") { const on = !map.streets(); map.setStreets(on); b.setAttribute("aria-pressed", String(on));
        $("#gstreetnote").innerHTML = on ? `Street pictures: <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener">&copy; OpenStreetMap contributors</a>. They come from OpenStreetMap&rsquo;s servers, which see which map squares are asked for; everything else stays on this device.`
          : `Street pictures are off. Switched on, they come from OpenStreetMap&rsquo;s servers, which see which map squares are asked for; everything else stays on this device.`; }
    });
    $("#glayer").addEventListener("change", e => setLayer(e.target.value));
    const inp = $("#gfind");
    inp.addEventListener("focus", () => fillFind(false));
    const go = () => { fillFind(false); const v = inp.value.trim().toLowerCase(); if (!v) return;
      const hit = found.find(x => x[0].toLowerCase() === v) || (found.filter(x => x[0].toLowerCase().startsWith(v)).length === 1 ? found.find(x => x[0].toLowerCase().startsWith(v)) : null);
      if (hit) { inp.value = hit[0]; show(map.layer(), hit[1]); } else side(`<p class="held">Nothing called &ldquo;${esc(inp.value)}&rdquo; among ${esc(words(map.layer())[0].toLowerCase())}. Pick a name from the list as you type.</p>${BACK()}`); };
    inp.addEventListener("change", go);
    inp.addEventListener("keydown", e => { if (e.key === "Enter") { e.preventDefault(); go(); } });
    return ready;
  }
  return {mount, locate, rough, show, view: () => map && map.view(), go: (lon, lat, z) => { if (map) map.goTo(lon, lat, z); }, layer: k => { if (k) setLayer(k); return map && map.layer(); },
    forget() { spot = box = null; if (map) { map.setPin(null); map.setMine(null); map.select(null); map.whole(); side(sideHome()); } },
    refresh() { if (map) { if (MINE && MINE.z) map.setMine(mineOf(MINE.z)); else { map.setMine(null); if (!spot) map.setPin(null); } side(sideHome()); } },
    unpin() { spot = box = null; if (map) map.setPin(null); },
    unmount() { if (map) { map.destroy(); map = null; } ready = null; }};
})();
