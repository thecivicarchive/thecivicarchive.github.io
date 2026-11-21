/* The chambers after November 3, as forecast (John, 2026-10-25): the map, the tiles, "inside the chamber" and each state's
   drill-down, one script for On The Ballot's and Election Night's Forecasts pages, reading one data file beside it. Every
   figure is the site's Analysis, added up from the race forecasts; a share is never written as 0 or 100 percent. The page
   names a box for it: <section data-chx data-hash="1" data-track="#..." data-method="..."></section>. */
(() => {
  const ME = document.currentScript; if (!ME) return;
  const BASE = new URL(".", ME.src).href, DV = ME.dataset.v || "", HTML = document.documentElement;
  const LOC = /(^|\s)ballot(\s|$)/.test(HTML.getAttribute("data-i18n") || "") && typeof I18 !== "undefined";
  /* English words where the page has no language layer (Election Night's pages stay English): the same message format */
  const EN = (() => {
    const AST = new Map(), esc = s => String(s).replace(/[&<>"]/g, c => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;"})[c]);
    const num = n => Number(n).toLocaleString("en-US"), rule = (n, o) => { try { return new Intl.PluralRules("en-US", {type: o ? "ordinal" : "cardinal"}).select(n); } catch (e) { return n === 1 ? "one" : "other"; } };
    function parse(msg) { let r = AST.get(msg); if (r) return r; let i = 0;
      const ws = () => { while (i < msg.length && /\s/.test(msg[i])) i++; };
      const word = () => { const m = /^[^\s,{}]+/.exec(msg.slice(i)); if (!m) throw 0; i += m[0].length; return m[0]; };
      function nodes(pl) { const out = []; let buf = "";
        while (i < msg.length) { const c = msg[i]; if (c === "{") { if (buf) { out.push(buf); buf = ""; } out.push(arg(pl)); continue; } if (c === "}") break;
          if (c === "#" && pl) { if (buf) { out.push(buf); buf = ""; } out.push({h: 1}); i++; continue; } buf += c; i++; }
        if (buf) out.push(buf); return out; }
      function arg(pl) { i++; ws(); const v = word(); ws(); if (msg[i] === "}") { i++; return {v}; } if (msg[i] !== ",") throw 0;
        i++; ws(); const k = word(); ws(); if (msg[i] === "}") { i++; return {v}; } if (msg[i] !== ",") throw 0; i++; const c = {};
        for (;;) { ws(); if (msg[i] === "}") { i++; break; } const s = word(); ws(); if (msg[i] !== "{") throw 0; i++; c[s] = nodes(pl || k === "plural" || k === "selectordinal"); if (msg[i] !== "}") throw 0; i++; }
        return {v, k, c}; }
      try { r = nodes(false); if (i < msg.length) r = [msg]; } catch (e) { r = [msg]; } AST.set(msg, r); return r; }
    function choose(ns, vals, out, n) { for (const x of ns) { if (typeof x === "string") out.push(x); else if (x.h) out.push(num(n)); else if (!x.k) out.push({val: vals[x.v]});
        else if (x.k === "plural" || x.k === "selectordinal") { const v = Number(vals[x.v]); choose(x.c["=" + v] || x.c[rule(v, x.k === "selectordinal")] || x.c.other || [], vals, out, v); }
        else choose(x.c[String(vals[x.v])] || x.c.other || [], vals, out, n); } return out; }
    const RAW = h => ({html: String(h)});
    const valText = (v, html) => { if (v && typeof v === "object" && "html" in v) return html ? v.html : v.html.replace(/<[^>]*>/g, ""); const s = typeof v === "number" ? num(v) : v == null ? "" : String(v); return html ? esc(s) : s; };
    const TAG = /<(\/?)(\d+)(\/?)>/g;
    const T = (msg, vals = {}) => choose(parse(msg), vals, []).map(p => typeof p === "string" ? p.replace(TAG, "") : valText(p.val, false)).join("");
    function TH(msg, vals = {}) { const stack = [{i: -1, out: ""}];
      for (const p of choose(parse(msg), vals, [])) { if (typeof p !== "string") { stack[stack.length - 1].out += valText(p.val, true); continue; } let last = 0;
        for (const m of p.matchAll(TAG)) { stack[stack.length - 1].out += esc(p.slice(last, m.index)); last = m.index + m[0].length; const k = +m[2], f = vals[k];
          if (m[3]) { stack[stack.length - 1].out += typeof f === "function" ? f("") : (f == null ? "" : String(f)); continue; }
          if (!m[1]) { stack.push({i: k, out: ""}); continue; } const top = stack.pop(); if (!top || top.i !== k || !stack.length) return esc(msg);
          stack[stack.length - 1].out += typeof f === "function" ? f(top.out) : top.out; }
        stack[stack.length - 1].out += esc(p.slice(last)); }
      return stack.length === 1 ? stack[0].out : esc(msg); }
    return {T, TH, RAW, num};
  })();
  const T = LOC ? I18.T : EN.T, TH = LOC ? I18.TH : EN.TH, RAW = LOC ? I18.RAW : EN.RAW, N_ = s => s;
  const num = n => LOC ? I18.num(n) : EN.num(n), place = n => LOC ? I18.place(n) : n;
  const day = iso => { try { return LOC ? I18.date(String(iso).slice(0, 10), {month: "long", day: "numeric", year: "numeric"}) : new Date(String(iso).slice(0, 10) + "T12:00:00Z").toLocaleDateString("en-US", {month: "long", day: "numeric", year: "numeric", timeZone: "UTC"}); } catch (e) { return String(iso).slice(0, 10); } };
  const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"}[c]));
  const nm = n => `<span translate="no">${esc(n)}</span>`;
  /* a share of the simulated elections or a chance: never 0 or 100 percent */
  const pc = x => x < 0.01 ? T("under 1%") : x > 0.99 ? T("over 99%") : (LOC ? I18.num(Math.round(x * 100) / 100, {style: "percent"}) : Math.round(x * 100) + "%");
  const one = x => LOC ? I18.num(Math.round(x * 10) / 10, {maximumFractionDigits: 1}) : String(Math.round(x * 10) / 10);      /* one decimal, the reader's way */
  const calm = () => HTML.classList.contains("calm") || HTML.dataset.motion === "reduced" || HTML.dataset.calm === "on" || matchMedia("(prefers-reduced-motion: reduce)").matches;
  const PV = {D: "var(--pD)", R: "var(--pR)", I: "var(--pI)", "": "var(--line-strong)"};
  const PW = {D: N_("Democrats"), R: N_("Republicans"), I: N_("Independents and others")};
  const PW1 = {D: N_("Democratic"), R: N_("Republican"), I: N_("Independent or other")};
  const MNPW = {D: N_("DFL"), R: N_("Republicans"), I: N_("Independents and others")};
  const CHN = {ussen: N_("U.S. Senate"), ushouse: N_("U.S. House"), gov: N_("Governors"), mnhouse: N_("Minnesota House of Representatives"), mnsen: N_("Minnesota Senate")};
  /* why a seat has no forecast yet, in the model's own terms */
  const WHY = {lines: N_("The state drew new congressional lines for 2026, and no past results on the new lines are on file, so the model has nothing to start this district from."),
    list: N_("The state's November candidate list for this race is not on file yet, so there is nothing to forecast."),
    past: N_("No past result on file describes this district."),
    third: N_("A candidate outside the two big parties is a main contender here; the model's party results do not describe that candidate's vote."),
    several: N_("Two or more candidates of one party share the ballot; past party results cannot split that party's vote among them."),
    nonp: N_("A nonpartisan office: the model is built on party results."), ticket: N_("Elected on one ticket with the governor."),
    multi: N_("Several seats are filled from one list; the model forecasts single-seat races only."),
    wall: N_("The state's November list for this race is not loaded yet."), none: N_("No forecast on file for this race yet.")};
  let DATA = null, DIST = null, BOX = null, OPT = {}, VIEW = "S", MODE = {}, ST = "", FIRST = true, NOW = null, LASTO = null;

  /* ---------- the data ---------- */
  const load = () => DATA ? Promise.resolve(DATA) : fetch(new URL("data/chambers.json?v=" + DV, BASE).href).then(r => r.ok ? r.json() : Promise.reject(r.status)).then(d => (DATA = d));
  const needDist = () => DIST ? Promise.resolve(DIST) : fetch(new URL(DATA.dist.url, BASE).href).then(r => r.ok ? r.json() : Promise.reject(r.status)).then(d => (DIST = d), () => (DIST = {q: 50, states: {}, failed: true}));
  const href = u => { try { return new URL(u, BASE).href; } catch (e) { return u; } };
  const urlOf = (s, ch) => href(((DATA.ch[ch] || {}).url || DATA.swurl).replace("{id}", s.id).replace("{st}", s.st.toLowerCase()));
  const stName = c => place((DATA && DATA.names[c]) || c);
  const fav = s => { const j = s.pr[0] >= s.pr[1] && s.pr[0] >= s.pr[2] ? 0 : s.pr[1] >= s.pr[2] ? 1 : 2; return {p: "DRI"[j], c: s.pr[j]}; };
  const tier = c => c >= DATA.tiers[0] ? "lk" : c >= DATA.tiers[1] ? "ln" : "tu";
  const pw = (ch, p) => T((ch === "mnhouse" || ch === "mnsen" ? MNPW : PW)[p]);

  /* a seat's name, as a sentence starts it */
  function seatTitle(s, ch){
    if (ch === "ussen") return T("U.S. Senate, {state}", {state: stName(s.st)}) + (s.sp ? " " + T("(special election)") : "");
    if (ch === "ushouse") return s.l ? T("U.S. House, {state}, District {d}", {state: stName(s.st), d: s.l}) : T("U.S. House, {state}, at large", {state: stName(s.st)});
    if (ch === "mnhouse") return T("Minnesota House, District {d}", {d: s.l});
    if (ch === "mnsen") return T("Minnesota Senate, District {d}", {d: s.l});
    if (ch === "gov") return T("Governor, {state}", {state: stName(s.st)});
    return s.o || "";
  }
  /* what is known or forecast about a seat, in words (the hover card, the dot's label and the state's lines) */
  function seatWords(s, ch, html){
    const h = seatHTML(s); if (html) return h;
    const d = document.createElement("div"); d.innerHTML = h; return d.textContent;      /* the same words as text, for a label */
  }
  function seatHTML(s){
    const who = n => RAW(nm(n));
    if (s.k === "n") return s.tn ? TH("Not up in 2026: {name} ({party}) holds it{y, select, none {} other {, next on the ballot in {y}}}.", {name: who(s.tn), party: T(PW1[s.t || "I"]), y: s.y ? String(s.y) : "none"})
      : TH("Not up in 2026.");
    if (s.k === "u") return TH("Only one party on the November ballot: {party}. That is a fact, not a forecast.", {party: T(PW1[s.p] || PW1.I)});
    if (s.k === "g") return TH("No forecast yet. {why}", {why: T(WHY[s.w] || WHY.none)});
    const f = fav(s), c = s.c[0];
    return c && c[1] === f.p ? TH("The model favours {name} ({party}): {chance} chance.", {name: who(c[0]), party: T(PW1[c[1]] || PW1.I), chance: pc(c[2])})
      : TH("The model favours the {party} side: {chance} chance.", {party: T(PW1[f.p]), chance: pc(f.c)});
  }
  const todayWords = (s, ch) => !s.t ? T("Vacant today.") : s.tn ? T("Held today by {name} ({party}).", {name: s.tn, party: T(PW1[s.t])}) : T("Held today by the {party} side.", {party: T(PW1[s.t])});

  /* ---------- the fills: party colour for party data only; patterns as well as colour ---------- */
  function defs(id, u){
    const w = u * 6, line = (p, op) => `<pattern id="${id}-ln-${p}" width="${w}" height="${w}" patternUnits="userSpaceOnUse" patternTransform="rotate(45)"><rect width="${w}" height="${w}" fill="${PV[p]}" fill-opacity=".28"/><rect width="${w / 2}" height="${w}" fill="${PV[p]}"/></pattern>`;
    const toss = p => `<pattern id="${id}-tu-${p}" width="${w}" height="${w}" patternUnits="userSpaceOnUse"><rect width="${w}" height="${w}" fill="var(--surface)"/><path d="M0 ${w / 2}H${w}M${w / 2} 0V${w}" stroke="${PV[p]}" stroke-width="${u * 1.1}"/></pattern>`;
    return `<defs>${["D", "R", "I"].map(p => line(p) + toss(p)).join("")}
      <pattern id="${id}-g" width="${w}" height="${w}" patternUnits="userSpaceOnUse" patternTransform="rotate(-45)"><rect width="${w}" height="${w}" fill="var(--line)"/><rect width="${w * .3}" height="${w}" fill="var(--line-strong)"/></pattern>
      <pattern id="${id}-n" width="${w}" height="${w}" patternUnits="userSpaceOnUse"><rect width="${w}" height="${w}" fill="var(--bg)"/><circle cx="${w / 2}" cy="${w / 2}" r="${u * .8}" fill="var(--line-strong)"/></pattern></defs>`;
  }
  function fill(s, id){
    if (!s) return `url(#${id}-n)`;
    if (s.k === "g") return `url(#${id}-g)`;
    if (s.k === "n") return `url(#${id}-n)`;
    if (s.k === "u") return PV[s.p] || PV.I;
    const f = fav(s), t = tier(f.c);
    return t === "lk" ? PV[f.p] : `url(#${id}-${t}-${f.p})`;
  }
  const legend = id => `<div class="chx-legend" data-lv="3" aria-hidden="true">${[["D", "lk", T("Likely (80% or more), or the only party on the ballot")], ["D", "ln", T("Leaning (60% to 80%)")], ["D", "tu", T("Toss-up (under 60%)")], ["", "g", T("No forecast yet")], ["", "n", T("Not up in 2026")]]
    .map(([p, t, w]) => `<span><svg viewBox="0 0 18 18">${t === "lk" ? `<rect width="18" height="18" rx="3" fill="${PV.D}"/><rect x="9" width="9" height="18" rx="0" fill="${PV.R}"/>` : t === "ln" || t === "tu" ? `<rect width="18" height="18" rx="3" fill="url(#${id}-${t}-D)"/>` : `<rect width="18" height="18" rx="3" fill="url(#${id}-${t})" stroke="var(--line-strong)"/>`}</svg>${esc(w)}</span>`).join("")}
    <span><svg viewBox="0 0 18 18"><rect width="9" height="18" fill="${PV.D}"/><rect x="9" width="9" height="18" fill="${PV.R}"/></svg>${esc(T("Party colours: Democratic, Republican"))}</span></div>`;

  /* ---------- the tiles ---------- */
  function tiles(ch, sum, seats){
    const P = ["D", "R"].concat(sum.hi.I ? ["I"] : []), today = todayOf(seats);
    let o = P.map(p => `<div class="chx-kpi p" style="--c:${PV[p]}"><span class="k">${esc(pw(ch, p))}</span><span class="v">${num(sum.med[p])}<small>${esc(T("seats"))}</small></span>
      <span class="s">${esc(sum.lo[p] === sum.hi[p] ? T("in nearly every simulated election") : T("likely {lo} to {hi}", {lo: num(sum.lo[p]), hi: num(sum.hi[p])}))} &middot; ${esc(T("today {n}", {n: num(today[p] || 0)}))}</span></div>`).join("");
    if (sum.ctl) o += `<div class="chx-kpi wide"><span class="k">${esc(T("Control"))}</span>${controlBar(sum)}<span class="s">${esc(control(ch, sum))}</span></div>`;
    const fl = sum.flip.D + sum.flip.R + sum.flip.I;
    o += `<div class="chx-kpi"><span class="k">${esc(T("Seats changing party"))}</span><span class="v">${esc(T("about {n}", {n: one(fl)}))}</span><span class="s">${esc(T("{d} to {pd}, {r} to {pr}, on average across the simulated elections", {d: one(sum.flip.D), pd: pw(ch, "D"), r: one(sum.flip.R), pr: pw(ch, "R")}))}${sum.flip.I >= 0.05 ? esc(T("; {n} to others", {n: one(sum.flip.I)})) : ""}</span></div>`;
    if (sum.grey) o += `<div class="chx-kpi"><span class="k">${esc(T("No forecast yet"))}</span><span class="v">${num(sum.grey)}<small>${esc(T("seats"))}</small></span><span class="s">${esc(T("Not counted for any party above. Tap a grey seat to see why."))}</span></div>`;
    return `<div class="chx-kpis" data-lv="2">${o}</div>`;
  }
  function controlBar(sum){
    const c = sum.ctl, w = v => (v * 100).toFixed(2) + "%";
    return `<span class="chx-bar" aria-hidden="true"><i style="width:${w(c.D)};background:${PV.D}"></i><i style="width:${w(c.dep + c.none)};background:var(--line-strong)"></i><i style="width:${w(c.R)};background:${PV.R}"></i></span>`;
  }
  /* control, under John's rule: settled only where a party reaches the majority counting none of the grey seats for it */
  function control(ch, sum){
    const c = sum.ctl, n = sum.grey, need = sum.need, D = pw(ch, "D"), R = pw(ch, "R");
    if (!sum.can.D && !sum.can.R) return (T("Only {k} of the {n} seats have a forecast, a known party or no race this year: fewer than the {m} a majority needs. So the {g} seats without a forecast decide control in every simulated election.", {k: num(sum.known), n: num(sum.n), m: num(Math.min(need.D, need.R)), g: num(n)}));
    let o = n ? T("Settled for {d} in {pd} of the simulated elections, for {r} in {pr}; in {px} it depends on the {g, plural, one {# seat} other {# seats}} without a forecast.", {d: D, pd: pc(c.D), r: R, pr: pc(c.R), px: pc(c.dep), g: n})
      : T("{d} hold a majority in {pd} of the simulated elections, {r} in {pr}.", {d: D, pd: pc(c.D), r: R, pr: pc(c.R)});
    if (c.none >= 0.0005) o += " " + T("In {pn}, neither party reaches a majority.", {pn: pc(c.none)});
    if (ch === "ussen") o += " " + T("A 50 to 50 tie goes to the Vice President's party, the Republicans; the two independents are counted with the Democrats, with whom they caucus.");
    return o;
  }
  const todayOf = seats => { const o = {D: 0, R: 0, I: 0, "": 0}; seats.forEach(s => { o[s.t || ""]++; }); return o; };

  /* ---------- inside the chamber: a half circle of seats, each a dot ---------- */
  function arcLayout(n){
    const rows = n <= 7 ? 1 : Math.max(2, Math.round(Math.sqrt(n / 4.4))), r0 = rows === 1 ? 1 : 0.4;
    const R = Array.from({length: rows}, (_, i) => rows === 1 ? 1 : r0 + (1 - r0) * i / (rows - 1)), tot = R.reduce((a, b) => a + b, 0);
    const per = R.map(r => Math.max(1, Math.floor(n * r / tot))); let left = n - per.reduce((a, b) => a + b, 0);
    for (let i = rows - 1; left > 0; i = (i - 1 + rows) % rows) { per[i]++; left--; }
    const pos = [];
    R.forEach((r, i) => { const k = per[i]; for (let j = 0; j < k; j++) { const a = k === 1 ? Math.PI / 2 : Math.PI * (1 - j / (k - 1)); pos.push({a, r, x: r * Math.cos(a), y: -r * Math.sin(a)}); } });
    pos.sort((p, q) => q.a - p.a || p.r - q.r);
    const gap = R.map((r, i) => per[i] > 1 ? Math.PI * r / (per[i] - 1) : 2);
    const dr = rows > 1 ? (1 - r0) / (rows - 1) : 1, rad = Math.min(Math.min(...gap) * 0.42, dr * 0.42, 0.09);
    return {pos, rad};
  }
  function seatScore(s, mode){
    const side = s.cc || s.t;
    if (mode === "t") return side === "D" ? 3 - (s.t === "I" ? 0.5 : 0) : side === "R" ? -3 : 0;
    if (s.k === "n") return side === "D" ? 4 - (s.t === "I" ? 0.3 : 0) : side === "R" ? -4 : 0;
    if (s.k === "u") return s.p === "D" ? 3 : s.p === "R" ? -3 : 0;
    if (s.k === "g") return 0;
    return 2 * (s.pr[0] - s.pr[1]);
  }
  function dotStyle(s, mode){
    if (mode === "t") { const p = s.t; return p ? `fill:${PV[p]};stroke:${PV[p]}` : `fill:var(--surface);stroke:var(--line-strong);stroke-dasharray:.02 .012`; }
    if (s.k === "n") { const p = s.t || "I"; return `fill:${PV[p]};stroke:${PV[p]};fill-opacity:.75`; }
    if (s.k === "u") return `fill:${PV[s.p]};stroke:${PV[s.p]}`;
    if (s.k === "g") return `fill:var(--line);stroke:var(--muted);stroke-dasharray:.02 .012`;
    const f = fav(s), t = tier(f.c);
    return t === "lk" ? `fill:${PV[f.p]};stroke:${PV[f.p]}` : t === "ln" ? `fill:${PV[f.p]};fill-opacity:.4;stroke:${PV[f.p]};stroke-width:.012` : `fill:var(--surface);stroke:${PV[f.p]};stroke-width:.014`;
  }
  function dotLabel(s, ch, mode){
    return `${seatTitle(s, ch)}. ${mode === "t" ? todayWords(s, ch) : seatWords(s, ch, false)}`;
  }
  function arcSVG(ch, seats, mode, key, sum){
    const L = arcLayout(seats.length), list = seats.map((s, i) => ({s, i, sc: seatScore(s, mode)})).sort((a, b) => b.sc - a.sc || (a.s.st + a.s.l).localeCompare(b.s.st + b.s.l));
    const r = L.rad, big = seats.length > 7;
    let o = "";
    list.forEach((x, k) => { const p = L.pos[k], s = x.s, sq = s.k === "n";
      const shape = sq ? `<rect x="${(p.x - r * .92).toFixed(4)}" y="${(p.y - r * .92).toFixed(4)}" width="${(r * 1.84).toFixed(4)}" height="${(r * 1.84).toFixed(4)}" rx="${(r * .25).toFixed(4)}"` : `<circle cx="${p.x.toFixed(4)}" cy="${p.y.toFixed(4)}" r="${(r * .92).toFixed(4)}"`;
      o += `${shape} class="seat" style="--i:${k};${dotStyle(s, mode)}" data-k="${key}" data-i="${x.i}" tabindex="${k ? -1 : 0}" role="button" aria-label="${esc(dotLabel(s, ch, mode))}"/>`; });
    const spec = key === ch ? DATA.ch[ch] : null;      /* the whole chamber (a state's delegation has no majority line) */
    if (spec && spec.maj && big) {      /* the majority line: between the seat that makes a majority and the next */
      const m = spec.maj, p = L.pos[Math.min(m, L.pos.length - 1)], q = L.pos[m - 1], a = (p.a + q.a) / 2;
      o += `<line class="maj" x1="${(0.33 * Math.cos(a)).toFixed(4)}" y1="${(-0.33 * Math.sin(a)).toFixed(4)}" x2="${(1.06 * Math.cos(a)).toFixed(4)}" y2="${(-1.06 * Math.sin(a)).toFixed(4)}"/>`;
    }
    const counts = todayOf(seats);
    let mid = "";
    if (big) {
      const line1 = mode === "t" ? T("Today: {d} {pd}, {r} {pr}", {d: num(counts.D), pd: pw(ch, "D"), r: num(counts.R), pr: pw(ch, "R")})
        : T("After November 3: about {d} {pd}, {r} {pr}{g, plural, =0 {} one {, and # seat with no forecast yet} other {, and # seats with no forecast yet}}", {d: num(sum.med.D), pd: pw(ch, "D"), r: num(sum.med.R), pr: pw(ch, "R"), g: sum.grey || 0});      /* the grey seats in the same line, so a total is never read as the whole chamber */
      const line2 = spec && spec.maj ? T("{m} seats make a majority", {m: num(spec.maj)}) : T("{n} seats", {n: num(seats.length)});
      mid = `<p class="chx-arccap"><b>${esc(line1)}</b><span>${esc(line2)}</span></p>`;      /* under the arc, in the page's own type */
    }
    return `<svg class="chx-arc${seats.length <= 20 ? " small" : ""}${FIRST && !calm() ? " chx-anim" : ""}" viewBox="-1.1 -1.1 2.2 1.2" role="group" aria-label="${esc(T("{chamber}: every seat as a dot", {chamber: T(CHN[ch] || ch)}))}">${o}</svg>${mid}`;
  }
  /* one chamber's diagram with its Today / After toggle, its card and its tables */
  function chamberHTML(ch, seats, sum, key, opts = {}){
    const mode = MODE[key] || "f";
    return `<div class="chx-chamber" data-key="${key}" data-ch="${ch}" data-lv="3">
      <div class="chx-tog" role="group" aria-label="${esc(T("Which picture"))}"><button type="button" data-m="t" aria-pressed="${mode === "t"}">${esc(T("Today"))}</button><button type="button" data-m="f" aria-pressed="${mode === "f"}">${esc(T("After November 3, as forecast"))}</button></div>
      ${arcSVG(ch, seats, mode, key, sum)}
      <div class="chx-panel chx-arcpanel" aria-live="polite" data-for="${key}">${esc(mode === "t" ? T("Each dot is a seat, in the colour of the party that holds it today. Squares are seats not up in 2026.") : T("Each dot is a seat. Solid: likely (80% or more) or one party only. Half-filled: leaning. A ring: toss-up. Dashed grey: no forecast yet. Squares: not up in 2026."))} ${esc(T("Point at a dot, or use the arrow keys, to see the seat."))}</div></div>
      ${tableHTML(ch, seats, sum)}`;
  }
  function tableHTML(ch, seats, sum){
    const today = todayOf(seats), P = ["D", "R", "I"];
    const row = p => `<tr><th scope="row">${esc(pw(ch, p))}</th><td>${num(today[p] || 0)}</td><td>${num(sum.med[p])}</td><td>${sum.lo[p] === sum.hi[p] ? num(sum.lo[p]) : esc(T("{lo} to {hi}", {lo: num(sum.lo[p]), hi: num(sum.hi[p])}))}</td></tr>`;
    const tr = sum.tiers || {}, cnt = k => tr[k] || 0;
    const how = [[T("Likely Democratic (80% or more)"), cnt("lkD")], [T("Leaning Democratic"), cnt("lnD")], [T("Toss-up"), cnt("tuD") + cnt("tuR") + cnt("tuI") + cnt("lnI") + cnt("lkI")], [T("Leaning Republican"), cnt("lnR")], [T("Likely Republican (80% or more)"), cnt("lkR")],
      [T("One party only on the ballot"), cnt("u")], [T("Not up in 2026"), cnt("n")], [T("No forecast yet"), cnt("g")]].filter(x => x[1]);
    return `<div class="chx-tw"><table class="chx-tbl"><caption>${esc(T("{chamber}: seats today and after November 3, as forecast. The middle and the likely range (8 in 10 of the simulated elections) count only seats with a forecast, one party on the ballot or no race this year.", {chamber: T(CHN[ch] || ch)}))}</caption>
      <thead><tr><th scope="col">${esc(T("Party"))}</th><th scope="col">${esc(T("Today"))}</th><th scope="col">${esc(T("After November 3: the middle"))}</th><th scope="col">${esc(T("Likely range"))}</th></tr></thead><tbody>
      ${P.filter(p => p !== "I" || today.I || sum.hi.I).map(row).join("")}${today[""] ? `<tr><th scope="row">${esc(T("Vacant today"))}</th><td>${num(today[""])}</td><td></td><td></td></tr>` : ""}
      ${sum.grey ? `<tr><th scope="row">${esc(T("No forecast yet"))}</th><td></td><td>${num(sum.grey)}</td><td></td></tr>` : ""}<tr><th scope="row">${esc(T("All seats"))}</th><td>${num(sum.n)}</td><td>${num(sum.n)}</td><td></td></tr></tbody></table></div>
      <div class="chx-tw" data-lv="2"><table class="chx-tbl"><caption>${esc(T("How sure the model is, seat by seat"))}</caption><tbody>${how.map(([w, n]) => `<tr><th scope="row">${esc(w)}</th><td>${num(n)}</td></tr>`).join("")}</tbody></table></div>`;
  }

  /* ---------- the map ---------- */
  const VB = () => { if (BOX) return BOX; let a = 1e9, b = 1e9, c = -1e9, d = -1e9; Object.values(DATA.box).forEach(x => { a = Math.min(a, x[0]); b = Math.min(b, x[1]); c = Math.max(c, x[2]); d = Math.max(d, x[3]); }); return BOX = [a - 4, b - 4, c - a + 8, d - b + 8]; };
  const bySt = (ch, st) => DATA.ch[ch].seats.filter(s => s.st === st);
  const decode = (ring, q) => { let x = 0, y = 0, o = ""; for (let i = 0; i < ring.length; i += 2) { x += ring[i]; y += ring[i + 1]; o += (i ? "L" : "M") + (x / q).toFixed(1) + "," + (y / q).toFixed(1); } return o + "Z"; };
  function mapSVG(view){
    const vb = VB(), id = "chxm", u = vb[2] / 900;
    let o = defs(id, u);
    const states = Object.keys(DATA.map).sort();
    if (view === "H" && !DIST) return `<p class="chx-sub" id="chxmap">${esc(T("Loading the district lines…"))}</p>`;
    if (view === "H") {
      states.forEach(st => { const seats = bySt("ushouse", st); if (!seats.length) { o += `<path class="dead" d="${DATA.map[st]}" style="fill:url(#${id}-n)"/>`; return; }
        const raw = DIST && DIST.states[st];
        if (seats.length === 1) { o += `<path data-ch="ushouse" data-id="${seats[0].id}" data-st="${st}" d="${DATA.map[st]}" style="fill:${fill(seats[0], id)}" tabindex="-1" role="button" aria-label="${esc(seatTitle(seats[0], "ushouse") + ". " + seatWords(seats[0], "ushouse"))}"/>`; return; }
        if (!raw) { const g = seats.filter(s => s.k === "g").length;
          o += `<path data-st="${st}" data-whole="1" d="${DATA.map[st]}" style="fill:url(#${id}-g)" tabindex="-1" role="button" aria-label="${esc(T("{state}: {n} House seats; {g} without a forecast", {state: stName(st), n: seats.length, g}))}"/>`; return; }
        const q = DIST.q || 50;
        Object.entries(raw).forEach(([n, rings]) => { const s = seats.find(x => String(x.l) === String(+n)); if (!s) return;
          o += `<path class="dist" data-ch="ushouse" data-id="${s.id}" data-st="${st}" d="${rings.map(r => decode(r, q)).join("")}" style="fill:${fill(s, id)}" tabindex="-1" role="button" aria-label="${esc(seatTitle(s, "ushouse") + ". " + seatWords(s, "ushouse"))}"/>`; });
        o += `<path class="out" d="${DATA.map[st]}"/>`; });
      states.forEach(st => { if (bySt("ushouse", st).length > 1 && !(DIST && DIST.states[st])) { const b = DATA.box[st]; o += `<text x="${((b[0] + b[2]) / 2).toFixed(1)}" y="${((b[1] + b[3]) / 2).toFixed(1)}" dy=".35em">${num(bySt("ushouse", st).length)}</text>`; } });
    } else {
      const ch = view === "S" ? "ussen" : "gov";
      states.forEach(st => { const s = DATA.ch[ch].seats.find(x => x.st === st && x.k !== "n");
        const lab = s ? seatTitle(s, ch) + ". " + seatWords(s, ch) : stName(st) + ". " + (st === "DC" ? T("No seat in this chamber.") : T("No race in 2026."));
        o += `<path data-ch="${ch}" data-st="${st}"${s ? ` data-id="${s.id}"` : ""} d="${DATA.map[st]}" style="fill:${s ? fill(s, id) : `url(#${id}-n)`}" tabindex="-1" role="button" aria-label="${esc(lab)}"${st === "DC" ? ` class="dead"` : ""}/>`; });
    }
    return `<svg class="chx-map" id="chxmap" viewBox="${vb.map(x => x.toFixed(1)).join(" ")}" role="group" aria-label="${esc(T("Map of the states: {view}", {view: T(view === "S" ? CHN.ussen : view === "H" ? CHN.ushouse : CHN.gov)}))}">${o}</svg>`;
  }
  function fitText(svg){ if (!svg || !svg.viewBox) return; const w = svg.getBoundingClientRect().width, vb = svg.viewBox.baseVal; if (w && vb) svg.style.setProperty("--fs", (12 * vb.width / w).toFixed(2) + "px"); }

  /* the card beside the map and under each chamber */
  function card(s, ch, withState){
    if (!s) return "";
    let o = `<b class="t">${esc(seatTitle(s, ch))}</b>`;
    o += `<p class="ln">${seatWords(s, ch, true)}</p>`;
    if (s.k === "f" && s.c[1]) o += `<p class="ln chx-sub">${TH("Then {name} ({party}): {chance}.", {name: RAW(nm(s.c[1][0])), party: T(PW1[s.c[1][1]] || PW1.I), chance: pc(s.c[1][2])})}</p>`;
    if (s.k !== "n") o += `<p class="ln chx-sub">${esc(todayWords(s, ch))}</p>`;
    if (s.k === "f") o += `<a class="chx-go" href="${esc(urlOf(s, ch))}">${esc(ch === "mnhouse" || ch === "mnsen" ? T("See this race's forecast") : T("Open the race's chart"))}</a>`;
    if (withState && s.st && s.st !== ST) o += `<div><button type="button" class="chx-btn" data-st="${s.st}">${esc(T("See {state} in detail", {state: stName(s.st)}))}</button></div>`;
    return o;
  }

  /* ---------- a state's drill-down ---------- */
  function stateHTML(st){
    const house = bySt("ushouse", st), sen = DATA.ch.ussen.seats.filter(s => s.st === st && s.k !== "n"), gov = DATA.ch.gov.seats.filter(s => s.st === st && s.k !== "n"), sw = DATA.sw[st] || [];
    let o = `<div class="chx-st" id="chxst"><h3>${esc(stName(st))}</h3><button type="button" class="chx-btn" data-back="1">${esc(T("Back to the whole country"))}</button>`;
    const D = DATA.deleg[st];
    if (house.length && D) {
      o += `<h4>${esc(T("U.S. House: {n, plural, one {# seat} other {# seats}}", {n: house.length}))}</h4>`;
      o += `<p data-lv-max="1">${esc(stSentence(st, D))}</p>`;
      o += (D.grey === D.n ? "" : tiles("ushouse", D, house)) + chamberHTML("ushouse", house, D, "h-" + st);
    }
    const lines = [...sen.map(s => [s, "ussen"]), ...gov.map(s => [s, "gov"]), ...sw.map(s => [s, "sw"])];
    if (lines.length) o += `<h4>${esc(T("Statewide races"))}</h4><ul class="chx-list">${lines.map(([s, ch]) => `<li><b>${esc(ch === "sw" ? s.o : seatTitle(s, ch))}</b>: ${seatWords(s, ch, true)}${s.k === "f" ? ` <a href="${esc(urlOf(s, ch))}">${esc(T("Open the race's chart"))}</a>` : ""}</li>`).join("")}</ul>`;
    else if (!house.length) o += `<p>${esc(T("No race for Congress or a statewide office here has a forecast yet."))}</p>`;
    o += `<div class="chx-esbox" data-es="${st}" data-h="4"></div>`;      /* the ballots already in, as forecast (earlysofar.js) */
    o += `<div class="chx-smbox" data-sm="${st}" data-chips="1"></div>`;      /* the state on the map, and "Your ballot, as forecast" (statemap.js) */
    if (st === "MN") {
      o += `<h4>${esc(T("The Minnesota Legislature"))}</h4><p class="chx-sub">${esc(T("Every seat in both chambers is on the ballot. DFL is the Democratic-Farmer-Labor Party, Minnesota's Democrats."))}</p>`;
      ["mnhouse", "mnsen"].forEach(ch => { const C = DATA.ch[ch];
        o += `<h3>${esc(T(CHN[ch]))}</h3><p data-lv-max="1">${esc(sentence(ch, C.sum))}</p>` + tiles(ch, C.sum, C.seats) + chamberHTML(ch, C.seats, C.sum, ch); });
    }
    /* every race of the state: the page's own list (On The Ballot: the list below, already showing the state) or its state page */
    if (OPT.list) o += `<p>${OPT.list.startsWith("#") && OPT.list.indexOf("{st}") < 0 ? `<button type="button" class="chx-btn" data-list="1">${esc(T("Every forecast in {state}, below", {state: stName(st)}))}</button>`
      : `<a href="${esc(OPT.list.replace("{st}", st))}">${esc(T("Every forecast in {state}", {state: stName(st)}))}</a>`}</p>`;
    return o + `</div>`;
  }
  const stSentence = (st, D) => D.grey === D.n ? T("None of {state}'s {n} House seats has a forecast yet.", {state: stName(st), n: D.n})
    : T("Of {state}'s {n} House seats, the model's simulated elections give Democrats about {d} and Republicans about {r}{g, plural, =0 {} one {; # seat has no forecast yet} other {; # seats have no forecast yet}}.", {state: stName(st), n: D.n, d: D.med.D, r: D.med.R, g: D.grey});

  /* the one plain sentence of a view (Beginner) */
  function sentence(ch, sum){
    const w = {ch: T(CHN[ch])};
    let o = T("If the model is right, {pd} would have about {d} seats in the {ch} and {pr} about {r}, counting the seats with a forecast, one party on the ballot or no race this year{g, plural, =0 {} one {; # seat has no forecast yet and is counted for no one} other {; # seats have no forecast yet and are counted for no one}}.", {pd: pw(ch, "D"), d: num(sum.med.D), pr: pw(ch, "R"), r: num(sum.med.R), ch: w.ch, g: sum.grey || 0});
    if (sum.ctl) o += " " + control(ch, sum);
    return o;
  }

  /* ---------- the whole block ---------- */
  function viewHTML(){
    const ch = VIEW === "S" ? "ussen" : VIEW === "H" ? "ushouse" : "gov", C = DATA.ch[ch], sum = C.sum;
    const tabs = [["S", CHN.ussen], ["H", CHN.ushouse], ["G", CHN.gov]];
    let o = `<div class="chx-tabs" role="group" aria-label="${esc(T("Which chamber"))}">${tabs.map(([v, w]) => `<button type="button" data-v="${v}" aria-pressed="${v === VIEW}">${esc(T(w))}</button>`).join("")}</div>`;
    o += `<p data-lv-max="1" class="chx-plain">${esc(VIEW === "G" ? govSentence(sum) : sentence(ch, sum))}</p>`;
    o += tiles(ch, sum, C.seats);
    o += `<div class="chx-mapgrid" data-lv="3"><div>${mapSVG(VIEW)}${legend("chxm")}${VIEW === "H" ? `<p class="chx-sub">${esc(T("Districts are drawn where the 2026 lines are the ones on file. A state that drew new lines for 2026 is shown whole, with its number of seats."))}</p>` : ""}</div>
      <aside class="chx-panel" id="chxpanel" aria-live="polite">${esc(VIEW === "H" ? T("Point at a district, or tap one, to see its race. Use the arrow keys inside the map to move from one to the next.") : T("Point at a state, or tap one, to see its race. Use the arrow keys inside the map to move from one to the next."))}</aside></div>`;
    o += `<h3 data-lv="3">${esc(T("Inside the chamber: {chamber}", {chamber: T(CHN[ch])}))}</h3>` + chamberHTML(ch, C.seats, sum, ch);
    return o;
  }
  const govSentence = sum => T("If the model is right, {pd} would hold about {d} governorships and {pr} about {r} after November 3, counting the {n} states with no race this year{g, plural, =0 {} one {; # race has no forecast yet} other {; # races have no forecast yet}}.", {pd: pw("gov", "D"), d: num(sum.med.D), pr: pw("gov", "R"), r: num(sum.med.R), n: (sum.tiers || {}).n || 0, g: sum.grey});
  function methodHTML(){
    const runs = DATA.runs;
    return `<details class="chx-method" data-lv="5"><summary>${esc(T("How the seats are added up"))}</summary>
      <p>${esc(T("Each race's chance is its latest forecast, the same one its chart shows. The seats are added up in {n} simulated elections. In each, every race is decided by where a number drawn for it falls among all the draws, so each race goes each way exactly as often as its own chance says, to within one draw.", {n: num(DATA.draws)}))}</p>
      <p>${esc(T("Races move together by the share of their uncertainty that the model itself calls shared. The national mood and the polls' common error are shared by every state; a state's own part by its races; in district races, the gap between House and statewide votes, a sitting member's edge and a region's swing by the races they touch. The rest is each race's own. Before a state's own polls, the model splits each state's uncertainty into those parts, and the split is used as it is."))}</p>
      <p>${esc(T("The draws start from the seed {seed}, made from the ids of the {n} model runs used, so the same runs always give the same counts.", {seed: DATA.seed, n: num(runs.length)}))}</p>
      <p>${TH("Control: a 50 to 50 Senate goes to the Vice President's party, since the Vice President votes only to break a tie (<0>the Constitution, Article I, section 3</0>); the Vice President is <1>{vp}</1>, a Republican. The Senate's own party-division page lists its two independents as caucusing with the Democrats (<2>Senate.gov</2>).", {vp: DATA.vp.name, 0: s => `<a href="${esc(DATA.vp.rule)}" rel="noopener">${s}</a>`, 1: s => `<a href="${esc(DATA.vp.who)}" rel="noopener">${s}</a>`, 2: s => `<a href="${esc(DATA.caucus)}" rel="noopener">${s}</a>`})}</p>
      <ul>${runs.map(r => `<li translate="no">${esc(r[0])}${r[3] ? " &middot; " + esc(r[3]) : ""}</li>`).join("")}</ul></details>`;
  }
  function render(root){
    if (!DATA) return;
    const t = OPT;
    let o = `<div class="chx-head"><h2 id="chx-h">${esc(T("After November 3: the chambers, as forecast"))}</h2><span class="tag analysis">${esc(T("Analysis"))}</span></div>`;
    o += `<p data-lv="2">${esc(T("The model forecasts each race on its own. Added up over many simulated elections, those forecasts give each party a likely number of seats, and a chance of control where the seats without a forecast cannot change the answer. Grey seats have no forecast yet and are counted for no one."))}</p>`;
    o += `<p class="chx-sub" data-lv="2">${TH("Forecasts as of {date}. This adding-up has no track record of its own: it adds up race forecasts that each have one. <0>See the track records</0>.", {date: day(DATA.asof), 0: s => `<a href="${esc(t.track || "#")}">${s}</a>`})}</p>`;
    o += `<div id="chxview">${viewHTML()}</div><div id="chxstate">${ST ? stateHTML(ST) : ""}</div>${methodHTML()}`;
    o += `<p class="chx-sub" data-lv="3">${TH("Not a result and not a call: the official count decides. <0>How the forecasts are made</0>.", {0: s => `<a href="${esc(t.method || "#")}">${s}</a>`})}</p>`;
    root.innerHTML = o;
    FIRST = false;
    wire(root);
    smount(root);
    if (VIEW === "H") needDist().then(() => { const v = root.querySelector("#chxview"); if (v && VIEW === "H") { v.innerHTML = viewHTML(); wireView(root); } });
  }

  /* ---------- the reader's moves ---------- */
  function seatOf(key, i){ const k = key.startsWith("h-") ? null : key; if (k && DATA.ch[k]) return [DATA.ch[k].seats[+i], k]; const st = key.slice(2); return [bySt("ushouse", st)[+i], "ushouse"]; }
  function roving(box, sel){
    box.addEventListener("keydown", e => { const items = [...box.querySelectorAll(sel)], i = items.indexOf(document.activeElement); if (i < 0) return;
      let j = null; if (e.key === "ArrowRight" || e.key === "ArrowDown") j = Math.min(items.length - 1, i + 1); else if (e.key === "ArrowLeft" || e.key === "ArrowUp") j = Math.max(0, i - 1); else if (e.key === "Home") j = 0; else if (e.key === "End") j = items.length - 1;
      if (j == null) return; e.preventDefault(); items[i].tabIndex = -1; items[j].tabIndex = 0; items[j].focus(); });
  }
  function wireChambers(root){
    root.querySelectorAll(".chx-chamber").forEach(box => {
      if (box.dataset.w) return; box.dataset.w = "1";
      const key = box.dataset.key, ch = box.dataset.ch, svg = box.querySelector("svg"), panel = box.querySelector(".chx-arcpanel");
      const ordered = [...svg.querySelectorAll(".seat")].sort((a, b) => +a.style.getPropertyValue("--i") - +b.style.getPropertyValue("--i"));
      ordered.forEach((el, k) => { el.tabIndex = k ? -1 : 0; svg.appendChild(el); });
      const show = el => { svg.querySelectorAll(".seat.on").forEach(x => x.classList.remove("on")); el.classList.add("on"); const [s, c] = seatOf(key, el.dataset.i); panel.innerHTML = MODE[key] === "t" ? `<b class="t">${esc(seatTitle(s, c))}</b><p class="ln">${esc(todayWords(s, c))}</p>` : card(s, c, key === ch && ch !== "mnhouse" && ch !== "mnsen"); };
      svg.addEventListener("focusin", e => { const el = e.target.closest(".seat"); if (el) show(el); });
      svg.addEventListener("click", e => { const el = e.target.closest(".seat"); if (el) { show(el); el.focus({preventScroll: true}); } });
      if (matchMedia("(hover: hover)").matches) svg.addEventListener("pointerover", e => { const el = e.target.closest(".seat"); if (el) show(el); });
      svg.addEventListener("keydown", e => { if (e.key === "Enter" || e.key === " ") { const el = e.target.closest(".seat"); if (el) { e.preventDefault(); show(el); } } });
      roving(svg, ".seat");
      box.querySelectorAll(".chx-tog button").forEach(b => b.addEventListener("click", () => { MODE[key] = b.dataset.m;
        const html = chamberHTML(ch, key.startsWith("h-") ? bySt("ushouse", key.slice(2)) : DATA.ch[ch].seats, key.startsWith("h-") ? DATA.deleg[key.slice(2)] : DATA.ch[ch].sum, key);
        const tmp = document.createElement("div"); tmp.innerHTML = html; box.replaceWith(tmp.firstElementChild); wireChambers(root);
        const nb = root.querySelector(`.chx-chamber[data-key="${key}"] .chx-tog button[data-m="${MODE[key]}"]`); if (nb) nb.focus(); }));
    });
  }
  function wireView(root){
    const map = root.querySelector("svg#chxmap"), panel = root.querySelector("#chxpanel");
    root.querySelectorAll(".chx-tabs button").forEach(b => b.addEventListener("click", () => { if (b.dataset.v === VIEW) return; VIEW = b.dataset.v; const v = root.querySelector("#chxview"); v.innerHTML = viewHTML(); wireView(root);
      const nb = root.querySelector(`.chx-tabs button[data-v="${VIEW}"]`); if (nb) nb.focus();
      if (VIEW === "H" && !DIST) needDist().then(() => { if (VIEW === "H") { v.innerHTML = viewHTML(); wireView(root); } }); }));
    if (map) {
      fitText(map);
      const paths = [...map.querySelectorAll("path[role=button]")]; if (paths.length) paths[0].tabIndex = 0;
      const show = (el, keep) => { if (!el || el.classList.contains("dead")) return; const st = el.dataset.st;
        map.querySelectorAll("path.hl").forEach(x => x.classList.remove("hl")); el.classList.add("hl");
        if (el.dataset.whole) { const seats = bySt("ushouse", st), g = seats.filter(s => s.k === "g");
          panel.innerHTML = `<b class="t">${esc(stName(st))}</b><p class="ln">${esc(T("{n} House seats. The state drew new district lines for 2026; {g, plural, =0 {every seat has a forecast} one {# seat has no forecast yet} other {# seats have no forecast yet}}.", {n: seats.length, g: g.length}))}</p><div><button type="button" class="chx-btn" data-st="${st}">${esc(T("See {state} in detail", {state: stName(st)}))}</button></div>`; return; }
        const ch = el.dataset.ch, s = el.dataset.id ? DATA.ch[ch].seats.find(x => x.id === el.dataset.id) : null;
        panel.innerHTML = s ? card(s, ch, true) : `<b class="t">${esc(stName(st))}</b><p class="ln">${esc(T("No race in 2026."))}</p><div><button type="button" class="chx-btn" data-st="${st}">${esc(T("See {state} in detail", {state: stName(st)}))}</button></div>`; };
      map.addEventListener("click", e => { const el = e.target.closest("path[role=button]"); if (el) show(el, true); });
      map.addEventListener("focusin", e => show(e.target.closest("path[role=button]")));
      map.addEventListener("keydown", e => { if (e.key === "Enter" || e.key === " ") { const el = e.target.closest("path[role=button]"); if (el) { e.preventDefault(); pick(el.dataset.st, true); } } });
      if (matchMedia("(hover: hover)").matches) map.addEventListener("pointerover", e => show(e.target.closest("path[role=button]")));
      roving(map, "path[role=button]");
    }
    wireChambers(root);
  }
  function wire(root){
    wireView(root);
    if (root.dataset.wired) return; root.dataset.wired = "1";
    root.addEventListener("click", e => {
      const l = e.target.closest("button[data-list]"); if (l) { const t = document.querySelector(OPT.list); if (t) t.scrollIntoView({block: "start", behavior: calm() ? "auto" : "smooth"}); return; }
      const b = e.target.closest("button[data-st], button[data-back]"); if (!b || !root.contains(b)) return; pick(b.dataset.back ? "" : b.dataset.st, true); });
  }
  /* a state picked (on the map, from the page's own choice, or from the address) */
  function pick(st, fromHere){
    st = st && DATA.names[st] ? st : "";
    if (st !== ST) { ST = st; const box = NOW && NOW.querySelector("#chxstate"); if (box) { box.innerHTML = ST ? stateHTML(ST) : ""; wireChambers(box); smount(box);
        if (fromHere && ST) { const h = box.querySelector("h3"); if (h) { h.tabIndex = -1; h.scrollIntoView({block: "start", behavior: calm() ? "auto" : "smooth"}); h.focus({preventScroll: true}); } } } }
    if (fromHere) {      /* the address follows (a copied link opens on the same state); the page's own list follows on On The Ballot */
      const q = new URLSearchParams(location.hash.slice(1)); if (ST) q.set("st", ST); else q.delete("st");
      const h = q.toString() ? "#" + q.toString() : ""; if (location.hash !== h) { history.replaceState(history.state, "", location.pathname + location.search + h); if (OPT.hash) dispatchEvent(new HashChangeEvent("hashchange")); }
    }
  }
  const smount = el => { const b = el && el.querySelector("[data-sm]"); if (b && window.SM) SM.mount(b); const e = el && el.querySelector("[data-es]"); if (e && window.ES) ES.mount(e); };
  function fromHash(){ const q = new URLSearchParams(location.hash.slice(1)); return {st: (q.get("st") || "").toUpperCase(), o: (q.get("o") || "").toUpperCase()}; }
  function mount(el){
    el = el || document.querySelector("[data-chx]"); if (!el) return;
    NOW = el; OPT = {hash: el.dataset.hash === "1", track: el.dataset.track || "", method: el.dataset.method || "", list: el.dataset.list || ""};
    if (!el.classList.contains("chx")) el.classList.add("chx");
    el.setAttribute("aria-labelledby", "chx-h");
    if (!document.getElementById("chx-css")) { const s = document.createElement("style"); s.id = "chx-css"; s.textContent = ".chx{margin:26px 0 0;border:1px solid var(--line);border-radius:18px;background:var(--surface);padding:16px 16px 18px;min-width:0;max-width:100%;box-sizing:border-box}\n.chx *{box-sizing:border-box}\n.chx h2{font-family:var(--serif);font-weight:400;font-size:clamp(26px,3.2vw,36px);line-height:1.1;margin:0}\n.chx h3{font:700 17px/1.3 var(--sans);margin:22px 0 0}\n.chx h4{font:700 12px var(--sans);letter-spacing:.09em;text-transform:uppercase;color:var(--muted);margin:18px 0 0}\n.chx p{margin:8px 0 0;max-width:80ch;line-height:1.5;font-size:15px}\n.chx .chx-sub{color:var(--muted);font-size:14px}\n.chx a{color:var(--accent-ink,var(--accent))}\n.chx-head{display:flex;gap:8px 12px;align-items:center;flex-wrap:wrap}\n.chx-tabs,.chx-tog{display:flex;flex-wrap:wrap;gap:6px;margin:14px 0 0}\n.chx-tabs button,.chx-tog button,.chx-btn{all:unset;box-sizing:border-box;cursor:pointer;min-height:40px;padding:0 15px;border-radius:999px;border:1px solid var(--line-strong);font:600 14px var(--sans);color:var(--ink);background:var(--surface);display:inline-flex;align-items:center;gap:6px}\n.chx-tabs button[aria-pressed=\"true\"],.chx-tog button[aria-pressed=\"true\"]{background:var(--ink);color:var(--bg);border-color:var(--ink)}\n.chx-tabs button:focus-visible,.chx-tog button:focus-visible,.chx-btn:focus-visible,.chx [role=button]:focus-visible,.chx a:focus-visible{outline:3px solid var(--accent);outline-offset:2px}\n@media (pointer:coarse){.chx-tabs button,.chx-tog button,.chx-btn{min-height:44px}}\n.chx-kpis{display:grid;grid-template-columns:repeat(auto-fill,minmax(min(100%,145px),1fr));gap:10px;margin:14px 0 0}\n.chx-kpi{border:1px solid var(--line);border-radius:14px;padding:10px 12px;background:var(--bg);min-width:0}\n.chx-kpi.p{border-left:5px solid var(--c)}\n.chx-kpi .k{font:700 11.5px var(--sans);letter-spacing:.08em;text-transform:uppercase;color:var(--muted);display:block}\n.chx-kpi .v{font-family:var(--serif);font-size:34px;line-height:1.05;display:block;margin:4px 0 2px;font-variant-numeric:tabular-nums}\n.chx-kpi .v small{font-family:var(--sans);font-size:14px;color:var(--muted);margin-left:4px}\n.chx-kpi .s{font-size:13px;color:var(--muted);line-height:1.4;display:block}\n.chx-kpi.wide{grid-column:1/-1}\n@media (min-width:640px){.chx-kpi.wide{grid-column:span 2}}\n.chx-bar{display:flex;height:12px;border-radius:6px;overflow:hidden;margin:8px 0 4px;background:var(--line)}\n.chx-bar i{display:block;height:100%}\n.chx-mapgrid{display:grid;grid-template-columns:minmax(0,1fr) minmax(220px,300px);gap:14px;margin:14px 0 0;align-items:start}\n@media (max-width:820px){.chx-mapgrid{grid-template-columns:minmax(0,1fr)}}\n.chx-map{width:100%;height:auto;display:block;overflow:visible}\n.chx-map>path{stroke:var(--surface);stroke-width:.6;vector-effect:non-scaling-stroke;cursor:pointer}\n.chx-map>path.dist{stroke-width:.35}\n.chx-map>path.out{fill:none;stroke:var(--ink);stroke-width:.8;pointer-events:none;opacity:.55}\n.chx-map>path.hl{stroke:var(--ink);stroke-width:1.8}\n.chx-map>path:focus{outline:none}.chx-map>path:focus-visible{stroke:var(--ink);stroke-width:2.6}\n.chx-map>path.dead{cursor:default}\n.chx-map text{fill:var(--ink);font:700 var(--fs,12px) var(--sans);text-anchor:middle;pointer-events:none;paint-order:stroke;stroke:var(--surface);stroke-width:3px}\n.chx-panel{border:1px solid var(--line);border-radius:14px;padding:12px 14px;background:var(--bg);font-size:14.5px;line-height:1.5;min-height:96px}\n.chx-panel b.t{display:block;font-size:15.5px}\n.chx-panel .ln{margin:6px 0 0}\n.chx-panel .dot{display:inline-block;width:10px;height:10px;border-radius:50%;background:var(--c);margin-right:6px}\n.chx-panel .chx-btn{margin-top:10px;min-height:40px;font-size:13.5px}\n.chx-go{display:inline-flex;align-items:center;min-height:40px;margin-top:8px;font-weight:700}\n.chx-legend{display:flex;flex-wrap:wrap;gap:6px 16px;margin:10px 0 0;font-size:13px;color:var(--muted);align-items:center}\n.chx-legend span{display:inline-flex;align-items:center;gap:6px}\n.chx-legend svg{width:18px;height:18px;flex:none}\n.chx-arc{width:100%;max-width:640px;height:auto;display:block;margin:10px auto 0;overflow:visible}\n.chx-arc.small{max-width:340px}\n.chx-arc .seat{cursor:pointer;stroke-width:.0065}\n.chx-arc .seat:focus{outline:none}\n.chx-arc .seat:focus-visible,.chx-arc .seat.on{stroke:var(--ink)!important;stroke-width:.014}\n.chx-arc .maj{stroke:var(--ink);stroke-width:.006;stroke-dasharray:.02 .015;opacity:.7}\n.chx-arccap{text-align:center;margin:6px auto 0!important;font-size:15px;line-height:1.4}\n.chx-arccap b,.chx-arccap span{display:block}.chx-arccap span{color:var(--muted);font-size:14px}\n.chx-anim .seat{animation:chxIn .5s ease-out both;animation-delay:calc(var(--i) * 1.6ms);transform-box:fill-box;transform-origin:center}\n@keyframes chxIn{from{opacity:0;transform:scale(.2)}to{opacity:1;transform:none}}\n:root.calm .chx-anim .seat,:root[data-motion=\"reduced\"] .chx-anim .seat{animation:none}\n@media (prefers-reduced-motion:reduce){.chx-anim .seat{animation:none}}\n.chx-arcpanel{margin:8px auto 0;max-width:640px}\n.chx-tw{overflow-x:auto;margin:12px 0 0;max-width:100%}\n.chx-tbl{border-collapse:collapse;font-size:14px;font-variant-numeric:tabular-nums;min-width:min(100%,420px)}\n.chx-tbl caption{text-align:left;font-size:13px;color:var(--muted);padding:0 0 6px;max-width:80ch}\n.chx-tbl th,.chx-tbl td{padding:6px 10px;border-bottom:1px solid var(--line);text-align:right;vertical-align:top}\n.chx-tbl th:first-child,.chx-tbl td:first-child{text-align:left}\n.chx-tbl thead th{font:700 12px var(--sans);letter-spacing:.04em;color:var(--muted)}\n.chx-st{margin:22px 0 0;border-top:2px solid var(--line-strong);padding-top:6px}\n.chx-st h3{font-family:var(--serif);font-weight:400;font-size:clamp(24px,3vw,32px);margin:12px 0 0}\n.chx-list{margin:8px 0 0;padding-left:20px;font-size:15px;line-height:1.5;max-width:86ch}\n.chx-list li{margin:6px 0}\n.chx-method{margin:18px 0 0;border:1px solid var(--line);border-radius:14px;padding:4px 14px}\n.chx-method summary{cursor:pointer;font-weight:700;min-height:40px;display:flex;align-items:center}\n.chx-method li{font-size:13.5px;margin:4px 0;overflow-wrap:anywhere}\n.chx-note{border-left:4px solid var(--brass,var(--line-strong));padding:4px 12px;color:var(--ink)}\n.chx .tag.analysis{flex:none}\n.chx-sr{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0);white-space:nowrap}"; document.head.appendChild(s); }
    const go = () => load().then(() => { const h = fromHash(); LASTO = h.o; if (["S", "H", "G"].includes(h.o)) VIEW = h.o; ST = h.st && DATA.names[h.st] ? h.st : ""; render(el); },
      () => { el.innerHTML = `<p class="chx-sub">${esc(T("The seat counts could not be loaded. Check your connection and open the page again."))}</p>`; });
    (LOC ? I18.ready : Promise.resolve()).then(go, go);
  }
  addEventListener("hashchange", () => { if (!DATA || !NOW || !NOW.isConnected) return; const h = fromHash(); pick(h.st, false); });
  document.addEventListener("fc:view", e => { if (!DATA || !NOW || !NOW.isConnected) return; const d = e.detail || {}; pick((d.st || "").toUpperCase(), false);
    const o = String(d.o || ""), moved = o !== LASTO; LASTO = o;      /* the office the reader just picked in the list, not one already there */
    if (moved && ["S", "H", "G"].includes(o) && o !== VIEW) { VIEW = d.o; const v = NOW.querySelector("#chxview"); if (v) { v.innerHTML = viewHTML(); wireView(NOW); if (VIEW === "H" && !DIST) needDist().then(() => { if (VIEW === "H") { v.innerHTML = viewHTML(); wireView(NOW); } }); } } });
  let rt = 0; addEventListener("resize", () => { clearTimeout(rt); rt = setTimeout(() => fitText(document.querySelector("svg#chxmap")), 150); });
  window.CHX = {mount};
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", () => mount()); else mount();
})();
