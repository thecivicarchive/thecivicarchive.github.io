/* splits.js - votes left blank, and places that chose different parties, race by race (John, 2026-11-08: "for each race
   ... see how many potential votes from someone's ballot they ended up NOT voting at all or if there was potentially some
   split ballot voting going on as well"). The site's build writes the data this script reads (night/splits/data/) and
   copies this script beside it; the build's own notes are the contract for both.

   One global, window.SPLITS (module.exports under node, for tests). Pure functions first (no page, no DOM): read the
   figures, work out the floors, the places that chose different parties, the margins side by side and the comparisons
   with 2024 and 2022; then render functions that return HTML strings (tables and one SVG dot chart). load() is the only
   function that asks for anything (fetch); a page that already holds the files passes them in instead.

   What a page does (the wiring is the page builders' step):
     const set  = SPLITS.readLive(stateDoc, {meta, status});        // /night-live/<base><code>.json, as published
     const res  = SPLITS.analyse({set, meta, race: "2026-PA-GOV", past: {"2024": SPLITS.readPast(y24), "2022": SPLITS.readPast(y22)}});
     box.innerHTML = SPLITS.render(res, {names: meta.cn, words: meta.uw});
   For Past results: set = SPLITS.readPast(yearDoc), race = a key of yearDoc.c ("2024-S"), past = the earlier years.
   For Minnesota's precincts: SPLITS.readLivePrecincts(stateDoc, [countyDoc ...], {meta}) and SPLITS.readPastPrecincts.
   A ballot page's tab does all of it in one call: SPLITS.fill(box, raceId, {js or data, live}).

   Reading levels (John, 2026-11-08): every table at every level (the floors' table in a box that scrolls, the comparisons'
   tables in folds that open from Hard); the dot chart from Medium; a line fitted through the dots and its r at Archivist
   only, with the warning beside it. render(res, {map: true}) adds a "Show these places on the map" button to each
   comparison with rows (data-spx-map: its index in res.vs, for mapClasses); the page wires it to its own map.

   The rules (binding; the words are John's):
   - Results by place cannot show any one voter's ballot. Nothing here says that voters split their tickets. The words
     are "places that chose different parties for these two races" and "the gap between the two races' margins".
   - The floor, in one unit (a county; a precinct in Minnesota): the votes in the unit's most-voted race that covers the
     whole unit, less the votes in this race, only where this race covers the whole unit too (a statewide race, or a
     House district that holds the whole county) and both are fully reported there. It is a floor: the true number of
     ballots left blank in this race is at least that, give or take ballots that did not carry this race (some overseas
     voters' ballots carry federal races only). Where the state reports ballots cast for the unit, ballots cast stand in
     for the top race; where it reports blank (under) votes for the race, those are shown as they are, with whose figure.
   - Margin: (the Democratic candidate's votes less the Republican candidate's) / every vote in the race, only when the
     race's top two are one Democrat and one Republican; no party margin, and no comparison, otherwise.
   - Fully reported: the unit's own [in, all] when the file gives it; else the race's [in, all]; else certified; else the
     state's word in now.json ("done": every unit in; "official": certified). Anything else is left out, and counted.
   - Years are compared only for the same kind of office, and the comparison says which office it is. */
(function (root) {
  "use strict";
  const FORMAT = 1, METHOD = "1.0";
  const FEDERAL = new Set(["P", "S", "H"]);
  const KIND_WORDS = {P: "President", S: "U.S. Senate", G: "Governor", H: "U.S. House"};

  /* ---------- small helpers ---------- */
  const esc = s => String(s == null ? "" : s).replace(/[&<>"']/g, c => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"}[c]));
  const num = n => (n == null || isNaN(n) ? "" : Math.round(n).toLocaleString("en-US"));
  const sum = a => a.reduce((s, x) => s + (x || 0), 0);
  const pct1 = x => (Math.round(x * 1000) / 10).toFixed(1);       /* a share as points with one decimal: .1234 -> "12.3" */

  /* ---------- parties (the same rule as history/realloc.party3) ---------- */
  function partyOf(party, wi) {
    if (wi) return "O";
    const p = String(party || "").trim().toUpperCase();
    if (!p) return "O";
    if (p.startsWith("DEM") || p === "D" || p === "DFL" || p.includes("DEMOCRAT") || /-NPL$/.test(p)) return "D";
    if (p.startsWith("REP") || p === "R" || p === "GOP" || p.includes("REPUBLICAN")) return "R";
    return "O";
  }
  /* a race's lines, as published (long or short form): [key, name as printed, party, write-in, name as filed] */
  const readLines = ch => (ch || []).map(c => { const wi = c.length > 3 && c[3] ? 1 : 0; return {name: c[1], party: c.length > 2 ? c[2] : null, wi, pc: partyOf(c.length > 2 ? c[2] : null, wi)}; });
  function topTwo(L, v) {      /* the two named lines with the most votes, in order; write-in lines left out */
    return L.map((l, i) => i).filter(i => !L[i].wi).sort((a, b) => (v[b] || 0) - (v[a] || 0) || a - b).slice(0, 2);
  }
  function partyPair(L, v) {   /* {d, r} line indexes when the race's top two are one Democrat and one Republican; else null */
    const t = topTwo(L, v);
    if (t.length < 2 || !((v[t[1]] || 0) > 0)) return null;
    const a = L[t[0]].pc, b = L[t[1]].pc;
    if (a === "D" && b === "R") return {d: t[0], r: t[1]};
    if (a === "R" && b === "D") return {d: t[1], r: t[0]};
    return null;
  }
  function unitRec(L, pair, two, vv, dn) {      /* one unit's figures: every vote (tot), and d, r, o (the best other named line) */
    const rec = {tot: sum(vv), done: dn === true, why: dn === true ? "" : dn};
    if (pair) {
      rec.d = vv[pair.d] || 0; rec.r = vv[pair.r] || 0; rec.o = 0;
      vv.forEach((x, i) => { if (i !== pair.d && i !== pair.r && !L[i].wi && (x || 0) > rec.o) rec.o = x || 0; });
    } else { rec.a = vv[two[0]] || 0; rec.b = two.length > 1 ? vv[two[1]] || 0 : 0; }
    return rec;
  }

  /* ---------- fully reported ---------- */
  /* true, or the reason a unit is left out: "counting" (some of its precincts are not in), "unknown" (the file does not
     say whether its count is complete) */
  function unitDone(inn, all, race, status) {
    if (inn != null && all != null && all > 0) return inn >= all ? true : "counting";
    if (race.off) return true;
    if (race.p && race.p[1] > 0) return race.p[0] >= race.p[1] ? true : "unknown";
    if (status === "done" || status === "official") return true;
    return "unknown";
  }

  /* ---------- reading the figures into one shape ----------
     A "set": {lvl: "county" | "precinct", code, at, status, final, year, races: {id: race}, ballots, bsrc, bnote, blank}
     race: {id, k (P S G H X), o (the office in words), names: [[name, party, code] x2], pair (null: no party margin),
            w (a Set of the units it covers whole, or null: every unit it lists), u: {unit: {tot, d, r, o | a, b, done, why}},
            listed: [units it should have], off, past} */
  function readLive(doc, opt) {
    opt = opt || {};
    const meta = opt.meta || {r: {}}, status = opt.status || doc.s || "", pre = doc.pre || "";
    const set = {lvl: "county", code: String(doc.state || meta.st || "").toUpperCase(), at: doc.at, status, final: status === "official",
      year: "2026", races: {}, ballots: null, bsrc: null, bnote: "", blank: opt.blank || null};
    for (const [key, e] of Object.entries(doc.r || {})) {
      const id = pre + key, m = (meta.r || {})[id];
      if (!m || !e.ch) continue;
      const L = readLines(e.ch), v = e.v || [], pair = partyPair(L, v), two = topTwo(L, v);
      const race = {id, k: m.k, o: m.o, L, v, pair, two, p: e.p || null, off: !!e.off, t: e.t || doc.at, u: {}, w: null, listed: null, novotes: !(sum(v) > 0),
        names: two.map(i => [L[i].name, L[i].party, L[i].pc])};
      if (pair) race.names = [[L[pair.d].name, L[pair.d].party, "D"], [L[pair.r].name, L[pair.r].party, "R"]];
      if (m.k === "H") { race.w = new Set(m.w || []); race.listed = (m.w || []).concat(m.s || []); }
      for (const [cu, ce] of Object.entries(e.k || {})) race.u[cu] = unitRec(L, pair, two, ce.slice(2), unitDone(ce[0], ce[1], race, status));
      if (!race.listed) race.listed = Object.keys(race.u);
      set.races[id] = race;
    }
    if (set.races && Object.values(set.races).some(r => r.off)) set.final = Object.values(set.races).every(r => r.off);
    /* ballots cast by county, from the state's own results file at one moment: used only when the figures on hand come
       from that same moment (the state file's "at"); else the floors stand alone and the page says why */
    const b = meta.b26;
    if (b && b.u) {
      if (b.at === doc.at) { set.ballots = {}; for (const [u, n] of Object.entries(b.u)) set.ballots[u] = [n, 0, 0]; set.bsrc = b.src || null; set.bwords = b.w || ""; }
      else set.bnote = "stale";
    }
    return set;
  }
  /* Minnesota's precincts on the night: the state file (for each race's lines) and the county files (<code>/c/<county>.json),
     as published. A precinct listed for a race has reported (store.encode_county); a precinct lies wholly inside its
     districts, so every race it lists covers it whole. */
  function readLivePrecincts(doc, countyDocs, opt) {
    opt = opt || {};
    const meta = opt.meta || {r: {}}, status = opt.status || "", pre = doc.pre || "";
    const set = {lvl: "precinct", code: String(doc.state || "").toUpperCase(), at: doc.at, status, final: status === "official", year: "2026",
      races: {}, ballots: null, bnote: "", blank: null, county: {}};
    const lineOf = {};
    for (const [key, e] of Object.entries(doc.r || {})) {
      const id = pre + key, m = (meta.r || {})[id];
      if (!m || !e.ch) continue;
      const L = readLines(e.ch), v = e.v || [], pair = partyPair(L, v), two = topTwo(L, v);
      lineOf[id] = L.length;
      set.races[id] = {id, k: m.k, o: m.o, L, v, pair, two, p: e.p || null, off: !!e.off, u: {}, w: null, listed: [], novotes: !(sum(v) > 0),
        names: pair ? [[L[pair.d].name, L[pair.d].party, "D"], [L[pair.r].name, L[pair.r].party, "R"]] : two.map(i => [L[i].name, L[i].party, L[i].pc])};
    }
    for (const cd of countyDocs || []) {
      if (!cd || !cd.u) continue;
      (cd.races || []).forEach((rid, k) => {
        const race = set.races[rid]; if (!race) return;
        const [runs, votes] = cd.r[k], idx = [];
        runs.forEach(x => { if (Array.isArray(x)) { for (let i = x[0]; i <= x[1]; i++) idx.push(i); } else idx.push(x); });
        const n = lineOf[rid] || (idx.length ? votes.length / idx.length : 0);
        idx.forEach((pi, j) => { const pid = cd.u[pi]; race.u[pid] = unitRec(race.L, race.pair, race.two, votes.slice(j * n, (j + 1) * n), true); race.listed.push(pid); set.county[pid] = cd.county; });
      });
    }
    return set;
  }
  /* a past year's county file (data/<code>-<year>.json): certified figures, every unit in */
  function readPast(doc, opt) {
    opt = opt || {};
    const set = {lvl: "county", code: doc.st, at: doc.e, status: "official", final: true, year: String(doc.y), races: {}, ballots: null, bsrc: null, bnote: "", blank: null,
      src: doc.src || {}};
    for (const [key, c] of Object.entries(doc.c || {})) set.races[key] = pastRace(key, c, doc.cu, c.u);
    if (doc.b && doc.b.u) { set.ballots = {}; doc.cu.forEach((u, i) => { if (doc.b.u[i]) set.ballots[u] = doc.b.u[i]; }); set.bsrc = (doc.src || {})[doc.b.s] || null; set.bwords = doc.b.w || ""; }
    return set;
  }
  /* a past year's precinct file for one Minnesota county (data/mn-<year>-p/<county>.json), with the year's county file for
     each contest's names and parties */
  function readPastPrecincts(yearDoc, pdoc) {
    const set = {lvl: "precinct", code: yearDoc.st, at: yearDoc.e, status: "official", final: true, year: String(yearDoc.y), races: {}, ballots: null, src: yearDoc.src || {},
      bsrc: null, bnote: "", blank: null, county: {}, pn: {}};
    for (const [key, arr] of Object.entries(pdoc.c || {})) { const c = yearDoc.c[key]; if (c) set.races[key] = pastRace(key, c, pdoc.pu, arr); }
    pdoc.pu.forEach((u, i) => { set.county[u] = pdoc.county; if (pdoc.pn) set.pn[u] = pdoc.pn[i]; });
    if (pdoc.b) { set.ballots = {}; pdoc.pu.forEach((u, i) => { if (pdoc.b[i]) set.ballots[u] = pdoc.b[i]; }); set.bsrc = (yearDoc.src || {})[(yearDoc.b || {}).s] || null; set.bwords = (yearDoc.b || {}).w || ""; }
    return set;
  }
  function pastRace(key, c, order, arr) {
    const race = {id: key, k: c.k, o: c.o, names: c.n || [], pair: c.dr ? {d: 0, r: 1} : null, u: {}, w: null, listed: [], off: true, past: true, d: c.d, cmp: c.cmp || [],
      s: c.s || [], sn: c.sn || 0};
    order.forEach((u, i) => {
      const x = arr[i]; if (!x) return;
      race.u[u] = c.dr ? {tot: x[0], d: x[1], r: x[2], o: x[3] || 0, done: true, why: ""} : {tot: x[0], a: x[1], b: x[2], done: true, why: ""};
      race.listed.push(u);
    });
    return race;
  }

  /* ---------- the floor ---------- */
  const covers = (race, u) => !race.w || race.w.has(u);
  /* the race with the most votes in unit u among the races that cover it whole and are fully reported there */
  function topIn(set, u, rid) {
    let best = null;
    for (const r of Object.values(set.races)) {
      const x = r.u[u];
      if (!x || !x.done || !(x.tot > 0) || !covers(r, u)) continue;
      if (!best || x.tot > best.tot || (x.tot === best.tot && r.id === rid)) best = {id: r.id, tot: x.tot};
    }
    return best;
  }
  /* the ballots that carried this race in a unit: ballots cast, less ballots that list only other races (Minnesota's
     federal-only and president-only absentee ballots, where the record gives them) */
  function carried(b, k) { return b[0] - (k === "P" ? 0 : b[2] || 0) - (FEDERAL.has(k) ? 0 : b[1] || 0); }
  function floors(set, rid) {
    const race = set.races[rid], out = {rows: [], left: [], listed: 0,
      sum: {floor: 0, v: 0, topV: 0, units: 0, exact: 0, exUnits: 0, exBad: 0, under: 0, over: 0, blUnits: 0, big: 0}};
    if (!race) return out;
    const units = new Set(race.listed.concat(Object.keys(race.u)));
    out.listed = units.size;
    for (const u of units) {
      const x = race.u[u];
      if (!covers(race, u)) { out.left.push({u, why: "split"}); continue; }
      if (!x) { out.left.push({u, why: "nofig"}); continue; }
      if (!x.done) { out.left.push({u, why: x.why || "counting"}); continue; }
      if (!(x.tot > 0)) { out.left.push({u, why: "novotes"}); continue; }
      const top = topIn(set, u, rid), row = {u, v: x.tot, top: top.id, topV: top.tot, floor: top.tot - x.tot};
      /* a gap of more than a tenth of the top race's votes is unusual: it is flagged, never changed (the page says the
         two races' figures may not cover the same ballots yet, and that the county's own report is the authority) */
      if (top.tot > 0 && row.floor / top.tot > 0.1) { row.big = 1; out.sum.big++; }
      const b = set.ballots && set.ballots[u];
      if (b) {
        const c = carried(b, race.k), blank = c - x.tot;
        if (blank >= 0 && b[0] >= top.tot) { row.ex = {kind: "ballots", n: b[0], carried: c, blank}; out.sum.exact += blank; out.sum.exUnits++; }
        else { row.exBad = 1; out.sum.exBad++; }
      }
      const bl = set.blank && set.blank[rid] && set.blank[rid][u];      /* blank (under) votes the state reports itself */
      if (bl) {
        row.ex = {kind: "blank", under: bl[0], over: bl[1] == null ? null : bl[1]};
        out.sum.under += bl[0] || 0; out.sum.over += bl[1] || 0; out.sum.blUnits++;
      }
      out.rows.push(row);
      out.sum.floor += row.floor; out.sum.v += row.v; out.sum.topV += row.topV; out.sum.units++;
    }
    out.rows.sort((a, b) => b.floor - a.floor || b.topV - a.topV);
    return out;
  }

  /* ---------- margins and the places that chose different parties ---------- */
  const marginOf = x => (x && x.tot > 0 ? (x.d - x.r) / x.tot : null);       /* D less R, as a share of every vote */
  function leadOf(x, pair) {        /* the party whose candidate had the most votes in the unit: D, R, O (someone else), tie */
    if (!pair || !x) return null;
    const m = Math.max(x.d, x.r);
    if ((x.o || 0) > m) return "O";
    return x.d > x.r ? "D" : x.r > x.d ? "R" : "tie";
  }
  /* the House race that covers unit u whole (a county, or a precinct), for "H*": each place's own House race */
  function houseIn(set, u) {
    for (const r of Object.values(set.races)) if (r.k === "H" && (r.w ? r.w.has(u) : !!r.u[u])) return r;
    return null;
  }
  function sideBySide(set, rid, oid) {
    const A = set.races[rid], out = {other: oid, rows: [], left: [], sum: null, none: ""};
    if (!A) return out;
    if (!A.pair) { out.none = A.novotes ? "novotes" : "this"; return out; }
    const fixed = oid === "H*" ? null : set.races[oid];
    if (oid !== "H*" && !fixed) { out.none = "missing"; return out; }
    if (fixed && !fixed.pair) { out.none = fixed.novotes ? "othernovotes" : "other"; return out; }
    let s = {da: 0, ra: 0, ta: 0, db: 0, rb: 0, tb: 0, split: 0, splitV: 0};
    for (const u of new Set(A.listed.concat(Object.keys(A.u)))) {
      const B = fixed || houseIn(set, u), x = A.u[u], y = B && B.u[u];
      if (!covers(A, u) || (B && !covers(B, u)) || (!fixed && !B && A.u[u])) { out.left.push({u, why: "split"}); continue; }
      if (!x || !y) { out.left.push({u, why: "nofig"}); continue; }
      if (!x.done || !y.done) { out.left.push({u, why: !x.done ? x.why || "counting" : y.why || "counting"}); continue; }
      if (!B.pair) { out.left.push({u, why: "noparty"}); continue; }
      if (!(x.tot > 0) || !(y.tot > 0)) { out.left.push({u, why: "novotes"}); continue; }
      const ma = marginOf(x), mb = marginOf(y), la = leadOf(x, A.pair), lb = leadOf(y, B.pair);
      const split = (la === "D" || la === "R") && (lb === "D" || lb === "R") && la !== lb;
      out.rows.push({u, other: B.id, va: x.tot, vb: y.tot, ma, mb, gap: ma - mb, la, lb, split});
      s.da += x.d; s.ra += x.r; s.ta += x.tot; s.db += y.d; s.rb += y.r; s.tb += y.tot;
      if (split) { s.split++; s.splitV += x.tot; }
    }
    out.rows.sort((p, q) => q.va - p.va);
    out.sum = {units: out.rows.length, split: s.split, splitV: s.splitV, ma: s.ta ? (s.da - s.ra) / s.ta : null, mb: s.tb ? (s.db - s.rb) / s.tb : null, va: s.ta, vb: s.tb};
    if (out.sum.ma != null && out.sum.mb != null) out.sum.gap = out.sum.ma - out.sum.mb;
    return out;
  }
  /* this race against the same place's margin in an earlier year (a past set's contest, by key) */
  function vsPast(set, rid, pastSet, key) {
    const A = set.races[rid], P = pastSet && pastSet.races[key], out = {key, year: pastSet ? pastSet.year : "", rows: [], left: [], sum: null, none: ""};
    if (!A) return out;
    if (!P) { out.none = "missing"; return out; }
    out.office = P.o; out.k = P.k; out.names = P.names;
    if (!A.pair) { out.none = A.novotes ? "novotes" : "this"; return out; }
    if (!P.pair) { out.none = "other"; return out; }
    let s = {da: 0, ra: 0, ta: 0, dp: 0, rp: 0, tp: 0, flip: 0};
    for (const u of new Set(A.listed.concat(Object.keys(A.u)))) {
      const x = A.u[u], y = P.u[u];
      if (!covers(A, u)) { out.left.push({u, why: "split"}); continue; }
      if (!x) { out.left.push({u, why: "nofig"}); continue; }
      if (!x.done) { out.left.push({u, why: x.why || "counting"}); continue; }
      if (!y) { out.left.push({u, why: "nopast"}); continue; }
      if (!(x.tot > 0) || !(y.tot > 0)) { out.left.push({u, why: "novotes"}); continue; }
      const m = marginOf(x), mp = marginOf(y), la = leadOf(x, A.pair), lp = leadOf(y, P.pair);
      const flip = (la === "D" || la === "R") && (lp === "D" || lp === "R") && la !== lp;
      out.rows.push({u, v: x.tot, vp: y.tot, m, mp, ch: m - mp, la, lp, flip});
      s.da += x.d; s.ra += x.r; s.ta += x.tot; s.dp += y.d; s.rp += y.r; s.tp += y.tot; if (flip) s.flip++;
    }
    out.rows.sort((p, q) => q.v - p.v);
    out.sum = {units: out.rows.length, m: s.ta ? (s.da - s.ra) / s.ta : null, mp: s.tp ? (s.dp - s.rp) / s.tp : null, v: s.ta, vp: s.tp, flip: s.flip};
    if (out.sum.m != null && out.sum.mp != null) out.sum.ch = out.sum.m - out.sum.mp;
    return out;
  }
  /* the races "places that split" compares a race with: the meta's top races (Senate and governor), else the past year's
     President, Senate and governor contests; then each place's own House race ("H*") for a statewide race */
  function othersFor(set, meta, rid) {
    const A = set.races[rid]; if (!A) return [];
    let ids = [];
    if (A.past) ids = Object.values(set.races).filter(r => ["P", "S", "G"].includes(r.k)).map(r => r.id);
    else ids = ((meta && meta.top) || []).filter(id => set.races[id]);
    ids = ids.filter(id => id !== rid);
    /* no Senate or governor's race: the two statewide races with the most votes that have a party margin */
    const total = r => Object.values(r.u).reduce((s, x) => s + (x.tot || 0), 0);
    if (!ids.length) ids = Object.values(set.races).filter(r => r.k === "X" && r.pair && r.id !== rid).sort((a, b) => total(b) - total(a)).slice(0, 2).map(r => r.id);
    if (A.k !== "H" && Object.values(set.races).some(r => r.k === "H")) ids.push("H*");
    return ids;
  }

  /* ---------- everything for one race ---------- */
  /* o: {set, meta (the state's index, data/<code>.json; optional for Past results), race, past: {"2024": set, ...},
         others: [race ids or "H*"] (default othersFor), cmp: [past keys] (default the meta's list for the race, or the past
         contest's own cmp)} */
  function analyse(o) {
    const set = o.set, A = set.races[o.race], meta = o.meta || {};
    const res = {v: FORMAT, m: METHOD, race: o.race, ok: !!A, lvl: set.lvl, code: set.code, at: set.at, status: set.status, final: set.final,
      year: set.year, k: A && A.k, o: A && A.o, names: A ? A.names : [], party: !!(A && A.pair), bnote: set.bnote, bsrc: set.bsrc, bwords: set.bwords || ""};
    if (!A) return res;
    res.novotes = !!A.novotes;
    res.nounits = !Object.keys(A.u).length;
    res.floors = floors(set, o.race);
    res.vs = (o.others || othersFor(set, meta, o.race)).map(oid => {
      const s = sideBySide(set, o.race, oid);
      s.office = oid === "H*" ? `U.S. House (each ${set.lvl === "precinct" ? "precinct" : "place"}'s own district)` : (set.races[oid] || {}).o || oid;
      s.oNames = oid === "H*" ? [] : (set.races[oid] || {}).names || [];
      return s;
    });
    const cmp = o.cmp || (A.past ? A.cmp : ((meta.r || {})[o.race] || {}).c) || [];
    res.past = cmp.map(key => { const y = String(key).slice(0, 4); return vsPast(set, o.race, (o.past || {})[y], key); }).filter(p => p.none !== "missing");
    res.missingPast = cmp.filter(key => !(o.past || {})[String(key).slice(0, 4)]);
    /* the record's sources for the figures shown: this contest's (a past year) and each earlier contest compared */
    const srcOf = (st, r) => ((r && r.s) || []).map(id => (st && st.src || {})[id]).filter(Boolean);
    res.sources = [{what: `${A.o}, ${set.year}`, list: srcOf(set, A), more: A.sn || 0}].concat(res.past.map(p => {
      const ps = (o.past || {})[p.year], P = ps && ps.races[p.key];
      return {what: `${p.office}, ${p.year}`, list: srcOf(ps, P), more: (P && P.sn) || 0};
    })).filter(x => x.list.length);
    return res;
  }
  /* each unit's look on a map: "split" (chose different parties for the two races), "same", or nothing (left out) */
  function mapClasses(res, which) {
    const vs = (res.vs || [])[which || 0], out = {};
    if (!vs) return out;
    vs.rows.forEach(r => { out[r.u] = r.split ? "split" : "same"; });
    return out;
  }

  /* ---------- words ---------- */
  const W = {
    cannotOne: "A county's totals cannot show any one ballot. A gap between two races can come from voters who chose different parties, from voters who skipped one race, and from third-party and write-in candidates.",
    cannotPlaces: "This compares places, not people, and a pattern across places is not a cause.",
    floor: "This is a floor, not a count. The true number of ballots left blank in this race is at least this many, because some ballots leave the top race blank too. A few ballots carry only some races (some overseas voters' ballots list federal races only), so a small part of a gap can be ballots that did not list this race.",
    ballots: "Ballots cast in the place, less the votes counted in this race: ballots left blank in this race, ballots marked for too many candidates, and any that did not list it.",
    pastCannot: "The same place holds different voters from one election to the next, and turnout in a midterm differs from turnout in a presidential year. A change in a place's margin does not say who changed, or why.",
    noParty: "This race's two leading candidates are not one Democrat and one Republican, so it has no party margin to compare."
  };
  const WHY = {split: "split between districts", nofig: "no figures for this race", counting: "still counting", unknown: "the file does not say whether its count is complete",
    novotes: "no votes recorded", noparty: "the other race has no party margin here", nopast: "not in the earlier record"};
  function unitWords(uw, lvl) {
    if (lvl === "precinct") return ["precinct", "precincts", "Precinct by precinct", "precinct by precinct", ""];
    return Array.isArray(uw) && uw.length >= 2 ? uw : ["county", "counties", "County by county", "county by county", " County"];
  }

  /* ---------- render (HTML strings; the pages' own CSS variables: --pD, --pR, --ink, --muted, --line, --surface, --accent) ----------
     Tables write a margin as D+12.3 or R+4.0 (the key under each table says what that means); sentences write it in words too. */
  const marginTxt = (m, cell) => {
    if (m == null) return "";
    const p = pct1(Math.abs(m));
    if (Math.abs(m) < 0.0005) return "even";
    const k = m > 0 ? "D" : "R";
    return cell ? `<span class="spx-m ${k}">${k}+${p}</span>`
      : `<span class="spx-m ${k}">${k}+${p}</span><span class="sr"> (the ${k === "D" ? "Democratic" : "Republican"} candidate ahead by ${p} points)</span>`;
  };
  /* a gap or a change between two margins, in points, and the party's candidate it leans toward (g > 0: toward the
     Democratic candidate in this race, compared with the other) */
  const gapTxt = (g, words) => {
    if (g == null) return "";
    const p = pct1(Math.abs(g));
    if (Math.abs(g) < 0.0005) return words ? "no gap" : "0";
    return words ? `${p} points toward the ${g > 0 ? "Democratic" : "Republican"} candidate` : `${p} ${g > 0 ? "D" : "R"}`;
  };
  const KEY = "D+ and R+: how many points the Democratic or the Republican candidate led by, as a share of every vote in the race.";
  function nameOf(u, o, set) {
    const n = (o.names || {})[u] || (set && set.pn && set.pn[u]);
    return n ? String(n) : u;
  }
  function asOf(res) {
    if (res.final || res.status === "official") return "as certified";
    return "as reported, not final";
  }
  const tag = () => `<span class="tag analysis">Analysis</span>`;
  const officeOf = res => res.o || KIND_WORDS[res.k] || "this race";
  const cap = s => String(s).charAt(0).toUpperCase() + String(s).slice(1);
  function officeShort(o, id) {
    const m = o.meta && o.meta.r && o.meta.r[id];
    if (m && m.o) return m.o;
    const r = o.set && o.set.races[id];
    return (r && r.o) || id;
  }
  function leftWords(F, uw) {
    if (!F.left.length) return "";
    const by = {};
    F.left.forEach(l => { by[l.why] = (by[l.why] || 0) + 1; });
    return "Left out: " + Object.entries(by).map(([w, n]) => `${num(n)} ${n === 1 ? uw[0] : uw[1]} (${WHY[w] || w})`).join("; ") + ".";
  }
  /* the one sentence for a race with nothing to work out yet, or "" */
  function emptyWords(res, uw) {
    if (res.novotes) return "No votes have been reported for this race yet.";
    if (res.nounits) return `The state's results file gives no ${uw[0]} figures for this race, so nothing here can be worked out ${uw[3]}.`;
    return "";
  }
  function renderFloors(res, o) {
    o = o || {};
    const F = res.floors, uw = unitWords(o.words, res.lvl), N = s => nameOf(s, o, o.set);
    if (!F) return "";
    const head = `<h3>Votes left blank ${tag()}</h3>`, empty = emptyWords(res, uw);
    if (empty) return `<section class="spx-floors">${head}<p>${esc(empty)}</p></section>`;
    if (!F.rows.length) {
      return `<section class="spx-floors">${head}<p>No ${esc(uw[0])} has a full count for this race yet (${asOf(res)}). ${leftWords(F, uw)}</p></section>`;
    }
    const exact = F.sum.exUnits > 0, blank = F.sum.blUnits > 0, units = n => esc(n === 1 ? uw[0] : uw[1]);
    /* an exact figure names whose figure it is */
    const whose = res.bsrc && res.bsrc.n ? ` Ballots cast from: ${esc(res.bsrc.n)}${res.final ? "" : " (as reported, not final)"}.` : "";
    const lede = `<p class="spx-lede">In the ${num(F.sum.units)} ${units(F.sum.units)}${res.final ? "" : " counted so far"}, this race had <b>at least ${num(F.sum.floor)} fewer votes</b> than the race with the most votes in each ${esc(uw[0])} (${asOf(res)}).`
      + (exact ? ` Where ballots cast are reported, ${num(F.sum.exact)} ballots in ${num(F.sum.exUnits)} ${units(F.sum.exUnits)} counted no vote in this race.${whose}` : "")
      + (blank ? ` The state reports ${num(F.sum.under)} blank votes in this race in ${num(F.sum.blUnits)} ${units(F.sum.blUnits)}${F.sum.over ? `, and ${num(F.sum.over)} ballots marked for too many candidates` : ""}.` : "") + `</p>`;
    const big = F.sum.big ? `<p class="spx-note">In ${num(F.sum.big)} ${units(F.sum.big)} (marked *) the gap is more than a tenth of the top race's votes. A gap that large can mean that the two races' figures do not cover the same ballots yet; the ${esc(uw[0])}'s own report is the authority.</p>` : "";
    const exCell = r => !r.ex ? (r.exBad ? "<small>does not add up</small>" : "")
      : r.ex.kind === "ballots" ? `${num(r.ex.blank)} <small>of ${num(r.ex.n)}</small>` : `${num(r.ex.under)}${r.ex.over != null ? ` <small>+${num(r.ex.over)} over</small>` : ""}`;
    const rows = F.rows.map(r => `<tr><th scope="row">${esc(N(r.u))}${r.big ? " *" : ""}</th><td>${num(r.v)}</td><td>${num(r.topV)} <small>${r.top === res.race ? "this race" : esc(officeShort(o, r.top))}</small></td>`
      + `<td><b>${num(r.floor)}</b></td>` + (exact || blank ? `<td>${exCell(r)}</td>` : "") + `</tr>`).join("");
    const exHead = blank ? "Blank votes the state reports" : res.bwords ? "Ballots with no vote counted in this race, of ballots cast" : "Exact figure";
    const table = `<div class="spx-tw"><table class="spx-t"><caption class="sr">Votes in this race against the race with the most votes, ${esc(uw[3])}</caption><thead><tr><th scope="col">${esc(cap(uw[0]))}</th><th scope="col">Votes in this race</th><th scope="col">Most votes in any race here</th><th scope="col">At least this many fewer</th>`
      + (exact || blank ? `<th scope="col">${esc(exHead)}</th>` : "") + `</tr></thead><tbody>${rows}</tbody></table></div>`;
    /* the table at every level (in a box that scrolls); the plain first sentence of the floor's caveat for Beginner and Easy */
    return `<section class="spx-floors">${head}${lede}<p data-lv-max="2">${esc(W.floor.split(". ")[0])}.</p>${big}${table}<p class="spx-cannot"><b>What this cannot tell you.</b> ${esc(W.floor)}${exact ? " " + esc(W.ballots) : ""}${res.bwords ? " " + esc(res.bwords) + "." : ""}</p>`
      + `<p class="spx-left">${leftWords(F, uw)}</p></section>`;
  }
  function dotChart(rows, o) {      /* x: the other race's margin, y: this race's, Democratic ahead to the left and down, Republican to the right and up; dot area by votes */
    o = o || {};
    const W0 = 360, H0 = 360, P = 44, lim = Math.min(1, Math.max(0.2, ...rows.map(r => Math.max(Math.abs(r.ma), Math.abs(r.mb))).map(x => Math.ceil(x * 10) / 10)));
    const X = m => P + (W0 - 2 * P) * (0.5 + (-m) / (2 * lim)), Y = m => H0 - P - (H0 - 2 * P) * (0.5 + (-m) / (2 * lim));
    const vmax = Math.max(1, ...rows.map(r => r.va)), R = v => 2 + 14 * Math.sqrt(v / vmax);
    const quad = `<rect x="${X(lim)}" y="${Y(-lim)}" width="${X(0) - X(lim)}" height="${Y(0) - Y(-lim)}" class="spx-q"/><rect x="${X(0)}" y="${Y(0)}" width="${X(-lim) - X(0)}" height="${Y(lim) - Y(0)}" class="spx-q"/>`;
    const short = m => Math.abs(m) < 0.0005 ? "even" : `${m > 0 ? "D" : "R"}+${pct1(Math.abs(m))}`;
    const dots = rows.slice().sort((a, b) => b.va - a.va).map(r => `<circle cx="${X(r.mb).toFixed(1)}" cy="${Y(r.ma).toFixed(1)}" r="${R(r.va).toFixed(1)}" class="spx-dot${r.split ? " s" : ""}"><title>${esc(nameOf(r.u, o, o.set))}: ${short(r.ma)} here, ${short(r.mb)} there, ${num(r.va)} votes</title></circle>`).join("");
    const lab = (x, y, t, a, cls) => `<text x="${x}" y="${y}" text-anchor="${a}" class="spx-ax${cls ? " " + cls : ""}">${esc(t)}</text>`;
    /* the fitted line (Archivist only): y = a + b x across the box, cut where it leaves the box */
    let fit = "";
    const F = o.fit;
    if (F) {
      const pts = [];
      [-lim, lim].forEach(x => { const y = F.a + F.b * x; if (Math.abs(y) <= lim + 1e-9) pts.push([x, y]); });
      if (Math.abs(F.b) > 1e-9) [-lim, lim].forEach(y => { const x = (y - F.a) / F.b; if (Math.abs(x) < lim - 1e-9) pts.push([x, y]); });
      if (pts.length >= 2) { pts.sort((p, q) => p[0] - q[0]); const p = pts[0], q = pts[pts.length - 1];
        fit = `<g data-lv="6"><line x1="${X(p[0]).toFixed(1)}" y1="${Y(p[1]).toFixed(1)}" x2="${X(q[0]).toFixed(1)}" y2="${Y(q[1]).toFixed(1)}" class="spx-fitl"/></g>`; }
    }
    return `<svg class="spx-dots" viewBox="0 0 ${W0} ${H0}" role="img" aria-label="${esc(o.label || "Each place as a dot: the other race's margin across, this race's margin up, sized by votes cast")}">`
      + quad + `<line x1="${X(lim)}" y1="${Y(lim)}" x2="${X(-lim)}" y2="${Y(-lim)}" class="spx-diag"/>`
      + `<line x1="${X(0)}" y1="${P}" x2="${X(0)}" y2="${H0 - P}" class="spx-axis"/><line x1="${P}" y1="${Y(0)}" x2="${W0 - P}" y2="${Y(0)}" class="spx-axis"/>` + dots + fit
      + lab(P, H0 - P + 16, "D ahead", "start", "D") + lab(W0 - P, H0 - P + 16, "R ahead", "end", "R") + lab(W0 / 2, H0 - 6, o.xLabel || "The other race's margin", "middle")
      + lab(P - 6, P + 4, "R", "end", "R") + lab(P - 6, H0 - P, "D", "end", "D") + `<text x="12" y="${H0 / 2}" transform="rotate(-90 12 ${H0 / 2})" text-anchor="middle" class="spx-ax">${esc(o.yLabel || "This race's margin")}</text>`
      + `</svg>`;
  }
  /* a straight line fitted through the dots by least squares, each place counted once (this race's margin on the other's):
     {a, b, r, n}, or null with fewer than three places or no spread across */
  function fitOf(rows) {
    const n = rows.length; if (n < 3) return null;
    let sx = 0, sy = 0; rows.forEach(p => { sx += p.mb; sy += p.ma; });
    const mx = sx / n, my = sy / n; let xx = 0, yy = 0, xy = 0;
    rows.forEach(p => { const dx = p.mb - mx, dy = p.ma - my; xx += dx * dx; yy += dy * dy; xy += dx * dy; });
    if (!(xx > 0) || !(yy > 0)) return null;
    const b = xy / xx;
    return {a: my - b * mx, b, r: xy / Math.sqrt(xx * yy), n};
  }
  const FITWARN = "A line drawn through places describes the places, not the people in them: it cannot say how any voter voted, and a close fit is not a cause.";
  function fitWords(F, uw) {
    if (!F) return "";
    const pts = Math.abs(F.a) < 0.0005 ? "0 points" : `${F.a > 0 ? "D+" : "R+"}${pct1(Math.abs(F.a))} points`;
    return `<p class="spx-fit" data-lv="6">${tag()} <b>The line through the dots</b> (least squares, each ${esc(uw[0])} counted once): this race's margin = ${pts} + ${F.b.toFixed(2)} &times; the other race's margin; r = ${F.r.toFixed(Math.abs(F.r) >= 0.995 ? 3 : 2)} across ${num(F.n)} ${esc(F.n === 1 ? uw[0] : uw[1])}. <b>Read it with care.</b> ${esc(FITWARN)}</p>`;
  }
  function noneWords(none, office) {
    if (none === "this") return W.noParty;
    if (none === "novotes") return "No votes have been reported for this race yet.";
    if (none === "other") return `${office}: its two leading candidates are not one Democrat and one Republican, so the two races cannot be set side by side by party.`;
    if (none === "othernovotes") return `${office}: no votes reported yet.`;
    return "";
  }
  function renderSplits(res, o) {
    o = o || {};
    const uw = unitWords(o.words, res.lvl), N = s => nameOf(s, o, o.set), units = n => esc(n === 1 ? uw[0] : uw[1]);
    if (emptyWords(res, uw)) return "";
    const parts = (res.vs || []).map((s, ix) => {
      const head = `<h4>${esc(officeOf(res))} and ${esc(s.office)}</h4>`;
      if (s.none) return noneWords(s.none, s.office) ? `<div class="spx-vs">${head}<p>${esc(noneWords(s.none, s.office))}</p></div>` : "";
      if (!s.rows.length) return `<div class="spx-vs">${head}<p>No ${esc(uw[0])} has a full count for both races yet (${asOf(res)}). ${leftWords(s, uw)}</p></div>`;
      const S = s.sum, list = s.rows.filter(r => r.split);
      const lede = `<p>${list.length ? `<b>${num(list.length)} of ${num(S.units)} ${units(S.units)}</b> chose different parties for these two races (${num(S.splitV)} votes in this race there).` : `All ${num(S.units)} ${units(S.units)} compared chose the same party for both races.`}`
        + (S.gap != null ? ` Added together, this race's margin there was ${marginTxt(S.ma)} and ${s.other === "H*" ? "the House races'" : esc(s.office) + "'s"} ${marginTxt(S.mb)}: the gap between the two races' margins is ${gapTxt(S.gap, true)} in this race.` : "") + `</p>`;
      const named = list.length ? `<p class="spx-list">${list.slice(0, 40).map(r => `${esc(N(r.u))} <small>(${r.la} here, ${r.lb} there)</small>`).join(", ")}${list.length > 40 ? `, and ${num(list.length - 40)} more` : ""}.</p>` : "";
      const rows = s.rows.map(r => `<tr${r.split ? ' class="spx-s"' : ""}><th scope="row">${esc(N(r.u))}</th><td>${marginTxt(r.ma, 1)}</td><td>${marginTxt(r.mb, 1)}${s.other === "H*" ? ` <small>${esc(officeShort(o, r.other).replace("U.S. House, ", ""))}</small>` : ""}</td><td>${gapTxt(r.gap)}</td><td>${num(r.va)}</td></tr>`).join("");
      const table = `<details class="spx-d" data-open-lv="4"><summary>Margins side by side, ${esc(uw[3])} (${num(S.units)})</summary><div class="spx-tw"><table class="spx-t"><thead><tr><th scope="col">${esc(cap(uw[0]))}</th><th scope="col">This race</th><th scope="col">${esc(s.office)}</th><th scope="col">Gap between the margins, in points</th><th scope="col">Votes in this race</th></tr></thead><tbody>${rows}</tbody></table></div><p class="spx-key">${esc(KEY)} Rows marked at the left: places that chose different parties for the two races.</p></details>`;
      /* the dot chart from Medium; the fitted line and its r at Archivist only, with the warning beside it */
      const F = fitOf(s.rows);
      const chart = `<figure class="spx-fig" data-lv="3">${dotChart(s.rows, {names: o.names, set: o.set, fit: F, xLabel: `${s.office}: margin`, yLabel: `${officeOf(res)}: margin`})}<figcaption>Each dot is a ${esc(uw[0])}, sized by the votes cast in this race. On the dashed line the two margins are equal; the shaded corners hold places that chose different parties for the two races.</figcaption>${fitWords(F, uw)}</figure>`;
      const mapb = o.map ? `<p class="spx-mapb"><button type="button" class="spx-mapbtn" data-spx-map="${ix}" aria-pressed="false">Show these places on the map</button></p>` : "";
      return `<div class="spx-vs">${head}${lede}${named}${mapb}${table}${chart}<p class="spx-left">${leftWords(s, uw)}</p></div>`;
    }).join("");
    if (!parts) return "";
    return `<section class="spx-splits"><h3>Places that chose different parties ${tag()}</h3>${parts}<p class="spx-cannot"><b>What this cannot tell you.</b> ${esc(W.cannotOne.replace("A county's", `A ${uw[0]}'s`))} ${esc(W.cannotPlaces)}</p></section>`;
  }
  function renderPast(res, o) {
    o = o || {};
    const uw = unitWords(o.words, res.lvl), N = s => nameOf(s, o, o.set), units = n => esc(n === 1 ? uw[0] : uw[1]);
    if (emptyWords(res, uw)) return "";
    const items = (res.past || []).map(p => {
      const what = `${p.office || p.key} in ${p.year}`, head = `<h4>Compared with ${esc(what)}${p.k !== res.k ? ` <small>(a different office)</small>` : ""}</h4>`;
      if (p.none) return `<div class="spx-past">${head}<p>${esc(p.none === "other" ? "That contest's two leading candidates were not one Democrat and one Republican, so it has no party margin to compare." : noneWords(p.none, what))}</p></div>`;
      if (!p.rows.length) return `<div class="spx-past">${head}<p>No ${esc(uw[0])} can be compared yet. ${leftWords(p, uw)}</p></div>`;
      const S = p.sum;
      const lede = `<p>In the ${num(S.units)} ${units(S.units)} compared, this race's margin was ${marginTxt(S.m)}; ${esc(what)}'s was ${marginTxt(S.mp)} (${num(S.vp)} votes, as certified). ${S.ch != null ? `A change of ${gapTxt(S.ch, true)}.` : ""}${S.flip ? ` ${num(S.flip)} ${units(S.flip)} chose a different party this time.` : ""}</p>`;
      const rows = p.rows.map(r => `<tr${r.flip ? ' class="spx-s"' : ""}><th scope="row">${esc(N(r.u))}</th><td>${marginTxt(r.m, 1)}</td><td>${marginTxt(r.mp, 1)}</td><td>${gapTxt(r.ch)}</td><td>${num(r.v)}</td><td>${num(r.vp)}</td></tr>`).join("");
      return `<div class="spx-past">${head}${lede}<details class="spx-d" data-open-lv="4"><summary>${esc(cap(uw[2]))} (${num(S.units)})</summary><div class="spx-tw"><table class="spx-t"><thead><tr><th scope="col">${esc(cap(uw[0]))}</th><th scope="col">This race</th><th scope="col">${esc(what)}</th><th scope="col">Change, in points</th><th scope="col">Votes now</th><th scope="col">Votes then</th></tr></thead><tbody>${rows}</tbody></table></div><p class="spx-key">${esc(KEY)} Rows marked at the left: places that chose a different party this time.</p></details><p class="spx-left">${leftWords(p, uw)}</p></div>`;
    }).join("");
    if (!items) return "";
    return `<section class="spx-pastall"><h3>Compared with earlier years ${tag()}</h3>${items}<p class="spx-cannot"><b>What this cannot tell you.</b> ${esc(W.pastCannot)} ${esc(W.cannotPlaces)}</p></section>`;
  }
  function renderSources(res, o) {
    o = o || {};
    const S = [];
    S.push(`Figures for ${res.year}: ${res.year === "2026" ? "the state's own results files, " + asOf(res) : "the state's certified canvass, as the record holds it"}.`);
    if (res.bsrc) S.push(`Ballots cast: ${esc(res.bsrc.n || "")}${res.bsrc.u ? ` (<a href="${esc(res.bsrc.u)}" rel="noopener">source</a>)` : ""}.`);
    if (res.bnote === "stale") S.push("The ballots-cast figures we hold are from an earlier moment than these figures, so they are not used until the next build.");
    (res.sources || []).forEach(x => S.push(`${esc(x.what)}: ${x.list.map(s => s.u && /^https?:/.test(s.u) ? `<a href="${esc(s.u)}" rel="noopener">${esc(s.n)}</a>` : esc(s.n)).join("; ")}`
      + (x.more ? `, and ${num(x.more)} more files the record read ${res.lvl === "precinct" ? "precinct by precinct" : "place by place"}` : "") + "."));
    if (o.meta && o.meta.lines && o.meta.lines.n) S.push(esc(o.meta.lines.n));
    S.push(`Method ${esc(METHOD)}. Margin: the Democratic candidate's votes less the Republican candidate's, as a share of every vote in the race. Floor: the most votes in any race that covers the whole ${res.lvl === "precinct" ? "precinct" : "place"}, less the votes in this race, where both are fully counted.`);
    return `<details class="spx-src" data-open-lv="5"><summary>Sources and methods</summary><ul>${S.map(s => `<li>${s}</li>`).join("")}</ul></details>`;
  }
  function render(res, o) {
    o = Object.assign({}, o || {});
    if (!res || !res.ok) return "";
    if (!o.names && o.meta && o.meta.cn) o.names = o.meta.cn;
    if (!o.words && o.meta && o.meta.uw) o.words = o.meta.uw;
    /* every view carries the line about what a county's totals cannot show: in the comparison section where there is one,
       else at the end of the view */
    const sp = renderSplits(res, o), uw = unitWords(o.words, res.lvl);
    const one = sp ? "" : `<p class="spx-cannot">${esc(W.cannotOne.replace("A county's", `A ${uw[0]}'s`))}</p>`;
    return `<div class="spx" data-race="${esc(res.race)}">` + (o.css === false ? "" : `<style>${CSS}</style>`) + renderFloors(res, o) + sp + renderPast(res, o) + one + renderSources(res, o) + `</div>`;
  }
  const CSS = `.spx{--spxD:var(--pD,#1238B8);--spxR:var(--pR,#A51E16);font-size:15px;line-height:1.5}
.spx h3{font-size:18px;margin:18px 0 6px}.spx h4{font-size:15.5px;margin:14px 0 4px}
.spx .spx-m.D{color:var(--spxD);font-weight:700;text-decoration:none}.spx .spx-m.R{color:var(--spxR);font-weight:700;text-decoration:none}
.spx-tw{overflow:auto;max-width:100%;max-height:30em;overscroll-behavior:contain}
.spx-t thead th{position:sticky;top:0;background:var(--surface,var(--bg,#fff));z-index:1}
.spx-t{border-collapse:collapse;font-variant-numeric:tabular-nums;font-size:14px;min-width:100%}
.spx-t th,.spx-t td{padding:4px 8px;border-bottom:1px solid var(--line,rgba(0,0,0,.14));text-align:right;white-space:nowrap}
.spx-t th[scope=row],.spx-t thead th:first-child{text-align:left}
.spx-t tr.spx-s th{box-shadow:inset 3px 0 0 var(--accent,#2F6B5E)}
.spx-cannot,.spx-left{color:var(--muted,#555);font-size:13.5px;max-width:80ch}
.spx-list{font-size:14px}
.spx-key,.spx-note{font-size:13px;color:var(--muted,#555);max-width:80ch}.spx-note{border-left:3px solid var(--accent,#2F6B5E);padding-left:8px}
.spx-fig{margin:10px 0;max-width:420px}.spx-fig figcaption{font-size:13px;color:var(--muted,#555)}
.spx-dots{width:100%;height:auto;display:block}
.spx-dots .spx-q{fill:color-mix(in srgb,var(--accent,#2F6B5E) 9%,transparent)}
.spx-dots .spx-diag{stroke:var(--muted,#777);stroke-dasharray:4 4}.spx-dots .spx-axis{stroke:var(--line,rgba(0,0,0,.25))}
.spx-dots .spx-dot{fill:color-mix(in srgb,var(--ink,#111) 28%,transparent);stroke:var(--ink,#111);stroke-opacity:.35;stroke-width:.6}
.spx-dots .spx-dot.s{stroke:var(--accent,#2F6B5E);stroke-opacity:1;stroke-width:1.6}
.spx-dots .spx-ax{font-size:11px;fill:var(--muted,#555)}.spx-dots .spx-ax.D{fill:var(--spxD)}.spx-dots .spx-ax.R{fill:var(--spxR)}
.spx-dots .spx-fitl{stroke:var(--brass,#A8762E);stroke-width:2.2;stroke-linecap:round}
.spx-fit{font-size:13px;margin:8px 0 0;padding:6px 8px;border-left:3px solid var(--brass,#A8762E);max-width:80ch}
.spx-d>summary{cursor:pointer;font-weight:600;min-height:40px;display:flex;align-items:center;gap:8px;list-style:none}.spx-d>summary::-webkit-details-marker{display:none}
.spx-d>summary::before{content:"";width:7px;height:7px;border-right:2px solid currentColor;border-bottom:2px solid currentColor;transform:rotate(-45deg);transition:transform .15s;flex:none}.spx-d[open]>summary::before{transform:rotate(45deg)}
.spx-pick{margin:10px 0 0}.spx-pick select{max-width:100%;min-height:40px;font:inherit}
.spx-mapb{margin:6px 0}:root[data-level="1"] .spx-mapb{display:none}.spx-mapbtn{font:600 13.5px/1.2 inherit;min-height:40px;padding:6px 12px;border-radius:999px;border:1px solid var(--accent,#2F6B5E);background:transparent;color:inherit;cursor:pointer}
.spx-mapbtn[aria-pressed=true]{background:var(--ink,#111);color:var(--bg,#fff);border-color:var(--ink,#111)}
.spx .sr{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0);white-space:nowrap}`;

  /* ---------- asking for the files (the only function that does) ---------- */
  /* o: {live: the live folder ("/night-live/"), data: the splits data folder (".../night/splits/data/"), years: ["2024", "2022"]}
     Returns {now, status, doc, meta, past: {year: set}, set} (set: readLive's, or null when the state has no figures). */
  function load(code, o) {
    o = o || {};
    const c = String(code).toLowerCase(), get = (u, init) => fetch(u, init).then(r => r.ok ? r.json() : null).catch(() => null);
    return Promise.all([o.live ? get(o.live + "now.json", {cache: "no-store"}) : null, get(o.data + c + ".json")]).then(([now, meta]) => {
      const st = now && now.st && now.st[c.toUpperCase()];
      const years = o.years || ["2024", "2022"];
      return Promise.all([st && st.f && now.base ? get(o.live + now.base + st.f, {cache: "force-cache"}) : null].concat(years.map(y => get(o.data + c + "-" + y + ".json"))))
        .then(([doc, ...ys]) => {
          const past = {}; ys.forEach((d, i) => { if (d) past[years[i]] = readPast(d); });
          const set = doc && meta ? readLive(doc, {meta, status: st && st.s}) : null;
          return {now, status: st && st.s, doc, meta, past, set};
        });
    });
  }

  /* ---------- the whole view in one box (the ballot pages' tab) ----------
     fill(box, raceId, {js: this script's address, or data: the data folder; live: the live folder}): loads the state's figures
     and files, works out the race and draws it, or says in one line why nothing can be worked out. Returns a promise. */
  let cssIn = false;
  function css() {
    if (cssIn || typeof document === "undefined") return;
    cssIn = true; const s = document.createElement("style"); s.textContent = CSS; document.head.appendChild(s);
  }
  function fill(box, race, o) {
    o = o || {}; css();
    const code = String(race).slice(5, 7), data = o.data || String(o.js || "").replace(/splits\.js[^/]*$/, "data/");
    const say = t => `<div class="spx"><p>${esc(t)}</p></div>`;
    return load(code, {live: o.live, data}).then(L => {
      const st = L.now && L.now.st && L.now.st[code.toUpperCase()];
      if (st && st.pt) box.innerHTML = say("This state's count is read here only in part (some counties' own figures, never the state's), so nothing here is worked out for it.");
      else if (st && st.s === "link") box.innerHTML = say("This site does not read this state's own count, so nothing here is worked out for it. The state's own results are linked from Election Night.");
      else if (!L.meta || !(L.meta.r || {})[race]) box.innerHTML = say("Nothing here is worked out for this race.");
      else if (!L.set || !L.set.races[race]) box.innerHTML = say("This race is not in the state's results file yet, so nothing here can be worked out.");
      else box.innerHTML = render(analyse({set: L.set, meta: L.meta, race, past: L.past}), {meta: L.meta, set: L.set, css: false});
      return L;
    });
  }

  /* ---------- Past results: one contest of a past year, by the record's own contest id ("<date>|<ST>|<slug>") ----------
     past(box, contestId, {data: the data folder, v: the indexes' version, map: draw the map buttons, onRes(res): the analysis
     on show, each time it changes}). Where the year's precinct files are kept (Minnesota), a list lets the reader look precinct by
     precinct in one county (with ballots cast, as certified); the comparisons with earlier years are made county by county only. */
  const NOPAST = "Nothing here is worked out for this contest. It covers President, U.S. Senate, U.S. House, governor and the statewide offices one person holds, where the record has figures county by county.";
  function past(box, cid, o) {
    o = o || {}; css();
    const m = /^(\d{4})-\d\d-\d\d\|([A-Z]{2})\|/.exec(cid || ""), say = t => `<div class="spx"><p>${esc(t)}</p></div>`;
    const get = f => fetch(o.data + f).then(r => r.ok ? r.json() : null).catch(() => null), tell = res => { if (o.onRes) o.onRes(res); };
    if (!m) { box.innerHTML = say(NOPAST); return Promise.resolve(null); }
    const y = m[1], code = m[2].toLowerCase();
    return get(code + ".json?v=" + (o.v || "")).then(meta => {
      const e = meta && meta.y && meta.y[y];
      if (!e) { box.innerHTML = say(NOPAST); return null; }
      return get(e.f + "?v=" + e.h).then(yd => {
        const key = yd && Object.keys(yd.c || {}).find(k => yd.c[k].id === cid);
        if (!key) { box.innerHTML = `<div class="spx"><p>${esc(NOPAST)}</p>${((yd && yd.gap) || []).map(g => `<p class="spx-left">${esc(g)}</p>`).join("")}</div>`; return null; }
        const ys = [...new Set((yd.c[key].cmp || []).map(k => String(k).slice(0, 4)))].filter(x => meta.y[x]);
        return Promise.all(ys.map(x => get(meta.y[x].f + "?v=" + meta.y[x].h))).then(ds => {
          const earlier = {}; ds.forEach((d, i) => { if (d) earlier[ys[i]] = readPast(d); });
          const set = readPast(yd), res = analyse({set, meta, race: key, past: earlier}), P = meta.p && meta.p[y];
          const cn = meta.cn || {}, cs = P ? P.c.slice().sort((a, b) => String(cn[a] || a).localeCompare(String(cn[b] || b))) : [];
          const uw = unitWords(meta.uw, "county");
          const pick = cs.length ? `<p class="spx-pick"><label>Look <select class="pick"><option value="">${esc(cap(uw[3]))}</option>${cs.map(c => `<option value="${esc(c)}">Precinct by precinct in ${esc(cn[c] || c)}</option>`).join("")}</select></label></p>` : "";
          box.innerHTML = pick + `<div class="spx-v">${render(res, {meta, set, css: false, map: o.map})}</div>`;
          const sel = box.querySelector(".spx-pick select"), v = box.querySelector(".spx-v");
          if (sel) sel.addEventListener("change", () => {
            const c = sel.value;
            if (!c) { v.innerHTML = render(res, {meta, set, css: false, map: o.map}); tell(res); return; }
            v.innerHTML = `<div class="spx"><p>Loading the precinct figures&hellip;</p></div>`;
            get(P.f + c + ".json?v=" + e.h).then(pd => {
              if (sel.value !== c) return;
              if (!pd) { v.innerHTML = say("The precinct figures could not be loaded. Check your connection and pick the county again."); return; }
              const ps = readPastPrecincts(yd, pd), pr = analyse({set: ps, race: key, past: {}});
              v.innerHTML = pr.ok ? render(pr, {set: ps, css: false}) + `<p class="spx-left">Precinct by precinct, the comparisons are with the same year's other races only; the earlier years are compared county by county.</p>` : say("This contest has no precinct figures in this county.");
              tell(pr.ok ? pr : null);
            });
          });
          tell(res);
          return res;
        });
      });
    });
  }

  const API = {FORMAT, METHOD, W, fitOf, fill, past, css, partyOf, readLines, partyPair, unitDone, readLive, readLivePrecincts, readPast, readPastPrecincts, topIn, floors,
    marginOf, leadOf, sideBySide, vsPast, othersFor, analyse, mapClasses, render, renderFloors, renderSplits, renderPast, renderSources, dotChart, load, CSS};
  if (typeof module === "object" && module.exports) module.exports = API;
  else root.SPLITS = API;
})(typeof window !== "undefined" ? window : globalThis);
