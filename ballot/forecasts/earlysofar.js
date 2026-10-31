/* The ballots already in, as forecast (John, 2026-10-26): for each state with an official count of ballots cast before Election
   Day, how those ballots probably lean, worked out from the race's forecast and counted history, and what the first figures on
   election night will likely show. One script for On The Ballot's and Election Night's Forecasts pages, reading data/es.json beside
   it and the state's live early-vote file when that is newer. A page names a box: <section data-es="FL" data-h="2"></section>.
   Every figure is Analysis; a share is never written as 0 or 100; registered party is shown apart and never used. */
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
  const num = n => LOC ? I18.num(n) : EN.num(n);
  const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"}[c]));
  const nm = n => `<span translate="no">${esc(n)}</span>`, nmR = n => RAW(nm(n));
  const url = rel => new URL(rel, BASE).href;
  const day = iso => { const s = String(iso || "").slice(0, 10); try { return LOC ? I18.date(s, {month: "long", day: "numeric", year: "numeric"})
    : new Date(s + "T12:00:00Z").toLocaleDateString("en-US", {month: "long", day: "numeric", year: "numeric", timeZone: "UTC"}); } catch (e) { return s; } };
  const pct = x => LOC ? I18.num(x, {style: "percent", maximumFractionDigits: 0}) : Math.round(x * 100) + "%";
  const one = x => LOC ? I18.num(Math.round(x * 100) / 100, {minimumFractionDigits: 2, maximumFractionDigits: 2}) : (Math.round(x * 100) / 100).toFixed(2);
  const sgn = x => (x >= 0 ? "+" : "−") + one(Math.abs(x));
  /* "the Florida Division of Elections" in English; another language's message carries its own article */
  const SN = S => LOC ? I18.place(S.n) : S.n;      /* a state's name in the reader's language */
  const thePub = p => /^the /i.test(p) || (LOC && !I18.en) ? p : "the " + p;
  const title = t => LOC && I18.has && I18.has(t, "office title") ? `${esc(t)} (${esc(I18.T(t, {}, "office title"))})` : esc(t);
  const PARTY = {DEM: N_("Democratic"), REP: N_("Republican"), NPA: N_("no party affiliation"), UNA: N_("unaffiliated"), OTH: N_("other parties"),
    IND: N_("Independent"), LIB: N_("Libertarian"), GRE: N_("Green"), GRN: N_("Green"), CST: N_("Constitution"), JFA: N_("Justice for All"),
    NLB: N_("No Labels"), WTP: N_("We the People")};
  const PC = {DEM: "var(--pD)", REP: "var(--pR)"};
  let DATA = null, P = null; const LIVE = {};
  const need = () => P || (P = fetch(url("data/es.json?v=" + DV)).then(r => r.ok ? r.json() : Promise.reject(new Error(String(r.status)))).then(d => (DATA = d), e => { P = null; throw e; }));
  /* the state's live early-vote file (refreshed each day), used when it is newer than the copy built in */
  const live = code => LIVE[code] || (LIVE[code] = fetch(url(DATA.live + code.toLowerCase() + ".json"), {cache: "no-cache"}).then(r => r.ok ? r.json() : null).catch(() => null));
  const fresh = (code, S, l) => l && l.v === 1 && l.st === code && String(l.t || "") >= String(S.ev.t || "") ? l : S.ev;

  /* ---------- the arithmetic (the build's own estimate is its twin, so the two always agree) ---------- */
  const Z = 1.2815515655446004, F_CAP = 0.98;
  const expit = x => x >= 0 ? 1 / (1 + Math.exp(-x)) : Math.exp(x) / (1 + Math.exp(x));
  const share = x => Math.min(99, Math.max(1, Math.floor(100 * expit(x) + 0.5)));
  function est(S, r, n) {
    const xc = r[5], sx = r[6], Tt = r[7]; let f = S.fs[0], fw = S.fs[1] ? "s" : "x";
    if (Tt && n && n / Tt > f) { f = Math.min(F_CAP, n / Tt); fw = "n"; }
    const gm = S.g[0], gs = S.g[1], q = (m, s) => [share(m - Z * s), share(m), share(m + Z * s)];
    return {f, fw, xB: xc + (1 - f) * gm, xR: xc - f * gm, B: q(xc + (1 - f) * gm, Math.hypot(sx, (1 - f) * gs)), R: q(xc - f * gm, Math.hypot(sx, f * gs)), F: q(xc, sx),
      first: S.ord === "dump" && S.blk === "pre" ? "B" : S.ord === "late" && S.blk === "mail" ? "R" : ""};
  }
  const countOf = (S, ev) => !ev || !ev.head ? 0 : S.blk === "mail" && S.ml ? ev.head.parts.filter(p => S.ml.includes(p[0])).reduce((a, p) => a + p[1], 0) || ev.head.n : ev.head.n;

  /* ---------- words ---------- */
  function leanWords(r, B, mail) {
    const a = r[3], b = r[4], [lo, mid, hi] = B;
    const v = {a: nmR(a), b: nmR(b), lo: num(lo), hi: num(hi)};
    if (mid >= 49 && mid <= 51) return mail ? TH("The mail ballots already in probably split about evenly between {a} and {b}: likely {lo} to {hi} in every 100 votes for the two would be for {a}.", v) : TH("The ballots already in probably split about evenly between {a} and {b}: likely {lo} to {hi} in every 100 votes for the two would be for {a}.", v);
    const who = mid > 50 ? a : b, p = mid > 50 ? mid : 100 - mid, l = mid > 50 ? lo : 100 - hi, h = mid > 50 ? hi : 100 - lo;
    Object.assign(v, {who: nmR(who), p: num(p), lo: num(l), hi: num(h)});
    let o = mail ? TH("The mail ballots already in probably lean toward {who}: about {p} in every 100 votes for {a} or {b}, likely {lo} to {hi}.", v) : TH("The ballots already in probably lean toward {who}: about {p} in every 100 votes for {a} or {b}, likely {lo} to {hi}.", v);
    if (lo < 50 && hi > 50) o += " " + esc(T("The likely range runs both ways."));
    return o;
  }
  function firstWords(S, r, E) {
    const st = SN(S), v = {state: st, a: nmR(r[3]), first: num(E.first === "B" ? E.B[1] : E.R[1]), fin: num(E.F[1])};
    if (E.first === "B") return TH("{state} releases its early and mail ballots first, so its first figures on election night will likely give {a} about {first} in every 100 votes for the two, moving toward about {fin} as Election Day ballots are counted.", v) + " " + esc(T("A move like that is how the count goes, not a sign that anything is wrong."));
    if (E.first === "R") return TH("{state} counts the ballots cast in person first and its mail ballots later, so its first figures on election night will likely give {a} about {first} in every 100 votes for the two, moving toward about {fin} as the mail ballots are counted.", v) + " " + esc(T("A move like that is how the count goes, not a sign that anything is wrong."));
    if (S.ord === "mail") return esc(T("{state} votes mostly by mail and counts its ballots in batches as they arrive, so its first figures on election night could lean either way, and they can move for days.", {state: st}));
    if (S.ord === "precinct") return esc(T("{state}'s counties report each precinct whole, early ballots and all, so its first figures on election night could lean either way.", {state: st}));
    if (S.ord === "late" || S.ord === "dump") return esc(T("{state} counts its ballots in two blocks, but its count here does not match one of them, so no estimate of its first figures is made.", {state: st}));
    return esc(T("How {state} orders its count has not been seen here, so its first figures on election night could lean either way.", {state: st}));
  }
  /* the small picture: the Democrat's share of the votes for the two, three rows of likely ranges, and where the first figures start */
  function pic(S, r, E) {
    const all = [...E.B, ...E.R, ...E.F, 50], lo = Math.max(0, Math.floor((Math.min(...all) - 3) / 5) * 5), hi = Math.min(100, Math.ceil((Math.max(...all) + 3) / 5) * 5);
    const W = 340, L = 6, Rr = 334, X = v => L + (v - lo) / (hi - lo) * (Rr - L), rowH = 36, mail = S.blk === "mail";
    const rows = [[mail ? T("Mail ballots") : T("Cast before Election Day"), E.B], [mail ? T("Cast in person") : T("Cast on Election Day"), E.R], [T("All ballots, the forecast"), E.F]];
    let o = "", y = 26;
    rows.forEach(([w, q]) => { o += `<text class="lb" x="${L}" y="${y - 11}">${esc(w)}</text><rect class="bar" x="${X(q[0]).toFixed(1)}" y="${y - 6}" width="${Math.max(2, X(q[2]) - X(q[0])).toFixed(1)}" height="12" rx="6"/><circle class="dot" cx="${X(q[1]).toFixed(1)}" cy="${y}" r="4.5"/>`; y += rowH; });
    if (E.first) { const a = X(E.first === "B" ? E.B[1] : E.R[1]), b = X(E.F[1]), dir = b >= a ? 1 : -1, tip = b - dir * 2;
      o += `<text class="lb" x="${L}" y="${y - 11}">${esc(T("First to final"))}</text>`;
      o += Math.abs(b - a) < 6 ? `<circle class="goh" cx="${b.toFixed(1)}" cy="${y}" r="4.5"/>` : `<path class="go" d="M${a.toFixed(1)} ${y}H${(tip - dir * 5).toFixed(1)}"/><path class="goh" d="M${tip.toFixed(1)} ${y}l${(-dir * 8).toFixed(1)} -5v10z"/>`;
      y += rowH; }
    const top = 18, bot = y - 22;
    o = `<line class="even" x1="${X(50).toFixed(1)}" x2="${X(50).toFixed(1)}" y1="${top}" y2="${bot}"/>` + o;
    const x50 = X(50);      /* the end labels only where they cannot run into "50, even" */
    o += `<line class="axis" x1="${L}" x2="${Rr}" y1="${bot + 4}" y2="${bot + 4}"/>${x50 - L > 64 ? `<text x="${L}" y="${bot + 18}">${esc(num(lo))}</text>` : ""}<text x="${x50.toFixed(1)}" y="${bot + 18}" text-anchor="${x50 - L < 30 ? "start" : Rr - x50 < 30 ? "end" : "middle"}">${esc(T("50, even"))}</text>${Rr - x50 > 64 ? `<text x="${Rr}" y="${bot + 18}" text-anchor="end">${esc(num(hi))}</text>` : ""}`;
    return `<svg class="espic" viewBox="0 0 ${W} ${bot + 24}" role="img" aria-label="${esc(mail ? T("{a}'s likely share of the votes for {a} or {b}: mail ballots {p1}, ballots cast in person {p2}, all ballots {p3}, each in every 100.", {a: r[3], b: r[4], p1: E.B[1], p2: E.R[1], p3: E.F[1]})
      : T("{a}'s likely share of the votes for {a} or {b}: ballots cast before Election Day {p1}, on Election Day {p2}, all ballots {p3}, each in every 100.", {a: r[3], b: r[4], p1: E.B[1], p2: E.R[1], p3: E.F[1]}))}">${o}</svg>
      <p class="escap">${E.first ? TH("{a}'s share of every 100 votes for {a} or {b}. Dots: the middle estimate; bars: the likely range, the middle 80% of the estimates; the arrow: from the first figures on election night to the expected final.", {a: nmR(r[3]), b: nmR(r[4])})
        : TH("{a}'s share of every 100 votes for {a} or {b}. Dots: the middle estimate; bars: the likely range, the middle 80% of the estimates.", {a: nmR(r[3]), b: nmR(r[4])})}</p>`;
  }
  const rng = q => `<b>${esc(num(q[1]))}</b> <small>${esc(T("likely {lo} to {hi}", {lo: num(q[0]), hi: num(q[2])}))}</small>`;
  function raceHTML(S0, r0, n, h) {
    /* everything about one race is told as the share of the candidate the forecast favours, so the words and the picture agree */
    const flip = est(S0, r0, n).F[1] < 50, r = flip ? [r0[0], r0[1], r0[2], r0[4], r0[3], -r0[5], r0[6], r0[7], r0[8], r0[9]] : r0;
    const S = flip ? Object.assign({}, S0, {g: [-S0.g[0], S0.g[1], S0.g[2], S0.g[3]]}) : S0, E = est(S, r, n), mail = S.blk === "mail";
    let o = `<div class="esr"><h${h}>${title(r[1])}</h${h}>`;
    o += `<p class="esone"><span class="tag analysis">${esc(T("Analysis"))}</span> ${leanWords(r, E.B, mail)}</p>`;
    o += `<p>${firstWords(S, r, E)}</p>`;
    o += `<div data-lv="2">${pic(S, r, E)}</div>`;
    o += `<dl class="esfig" data-lv="3"><dt>${esc(mail ? T("Mail ballots, already in and still to come: share for {a}", {a: r[3]}) : T("Ballots cast before Election Day: share for {a}", {a: r[3]}))}</dt><dd>${rng(E.B)}</dd>
      <dt>${esc(mail ? T("Ballots cast in person: share for {a}", {a: r[3]}) : T("Ballots cast on Election Day: share for {a}", {a: r[3]}))}</dt><dd>${rng(E.R)}</dd>
      <dt>${esc(T("All ballots, the race's forecast: share for {a}", {a: r[3]}))}</dt><dd>${rng(E.F)}</dd></dl>`;
    o += `<p class="esmath" data-lv="5">${esc(T("The arithmetic: x, the forecast's middle estimate of {a}'s share in log-odds, is {x} with a spread of {sx}; g, the starting gap, is {g} with a spread of {gs}; f is {f}. The first block is x + (1 − f) × g = {xb}; the second is x − f × g = {xr}. The two spreads add as independent errors, so each likely range is worked out exactly, with no random draws.", {a: r[3], x: sgn(r[5]), sx: one(r[6]), g: sgn(S.g[0]), gs: one(S.g[1]), f: one(E.f), xb: sgn(E.xB), xr: sgn(E.xR)}))}</p>`;
    if (r[8]) o += `<p class="essub"><a href="${esc(url(r[8]))}">${esc(T("Open the race's chart"))}</a></p>`;
    return o + `</div>`;
  }
  function otherHTML(S, rs, n) {
    if (!rs.length) return "";
    const mail = S.blk === "mail";
    const hd = `<tr><th scope="col">${esc(T("Race"))}</th><th scope="col">${esc(T("Democrat"))}</th><th scope="col" class="n">${esc(mail ? T("Mail ballots") : T("Cast before Election Day"))}</th><th scope="col" class="n">${esc(mail ? T("Cast in person") : T("Cast on Election Day"))}</th><th scope="col" class="n">${esc(T("All ballots"))}</th></tr>`;
    const body = rs.map(r => { const E = est(S, r, n); return `<tr><th scope="row">${r[8] ? `<a href="${esc(url(r[8]))}">${title(r[1])}</a>` : title(r[1])}</th><td>${nm(r[3])}</td><td class="n">${esc(num(E.B[1]))}</td><td class="n">${esc(num(E.R[1]))}</td><td class="n">${esc(num(E.F[1]))}</td></tr>`; }).join("");
    return `<details data-lv="2" data-open-lv="5"><summary>${esc(T("Other statewide races ({n})", {n: rs.length}))}</summary><p class="essub">${esc(T("Each figure is the Democrat's likely share of every 100 votes for the Democrat or the Republican. Analysis."))}</p><div class="estw"><table><thead>${hd}</thead><tbody>${body}</tbody></table></div></details>`;
  }
  function partyHTML(ev, h) {
    const P = ev.party; if (!P || !P.rows || !P.rows.length || !ev.head) return "";
    const kinds = P.cols.map(c => c[0]), use = kinds.includes("total_cast") ? ["total_cast"] : [kinds.includes("returned") ? "returned" : kinds.includes("accepted") ? "accepted" : "", "early_in_person"].filter(k => k && kinds.includes(k));
    if (!use.length) return "";
    const rows = P.rows.map(([p, vals]) => { const v = use.map(k => vals[kinds.indexOf(k)]).filter(x => x != null); return [p, v.length ? v.reduce((a, b) => a + b, 0) : null]; }).filter(x => x[1] != null);
    if (!rows.length) return "";
    const sum = rows.reduce((a, x) => a + x[1], 0), same = String(P.at || "").slice(0, 10) === String(ev.head.at || "").slice(0, 10), rest = same && ev.head.n > sum ? ev.head.n - sum : 0, base = sum + rest || 1;
    const tr = (lab, v, p) => `<tr${p ? ` data-p="${esc(p)}" style="--pc:${PC[p] || "var(--line-strong)"}"` : ""}><th scope="row">${lab}</th><td class="n">${esc(num(v))}</td><td class="n">${esc(pct(v / base))}</td></tr>`;
    const body = rows.map(([p, v]) => tr(`${esc(p)}${PARTY[p] ? ` <small>(${esc(T(PARTY[p]))})</small>` : ""}`, v, p)).join("") + (rest ? tr(esc(T("Other parties and no party, not listed by party in the state's file")), rest, "") : "");
    return `<div class="esparty" data-lv="2"><h${h}>${esc(T("The ballots already in, by the voter's registered party"))}</h${h}>
      <p class="esnote">${esc(T("Registration is not a vote: a registered Democrat may vote Republican, and many voters belong to no party. This table is never used in the estimate above."))}</p>
      <div class="estw"><table><thead><tr><th scope="col">${esc(T("Registered as"))}</th><th scope="col" class="n">${esc(T("Ballots already in"))}</th><th scope="col" class="n">${esc(T("Share"))}</th></tr></thead><tbody>${body}</tbody></table></div>
      <p class="essub">${esc(T("As the state's file gives them, as of {date}.", {date: day(P.at)}))}</p></div>`;
  }
  function pastWords(S) {
    const h = S.h22 || {};
    if (h.pre) return T("In 2022 about {pre} ballots were cast in {state} before Election Day, {p} of the {all} cast in all, as the state reported them afterwards to the U.S. Election Assistance Commission.", {pre: num(Math.round(h.pre / 1000) * 1000), state: SN(S), p: pct(h.pre / h.all), all: num(Math.round(h.all / 1000) * 1000)});
    const why = {coverage: N_("too few of its election offices reported every kind of ballot"), parts: N_("its kinds of ballot did not add up to its total"),
      total: N_("its total did not match the official vote closely enough"), kinds: N_("it did not report its ballots by kind")};
    return why[h.why] ? T("The 2022 survey of election offices is not used for {state}: {why}.", {state: SN(S), why: T(why[h.why])}) : T("No 2022 figure for {state} is on file.", {state: SN(S)});
  }
  function fWords(S, E) {
    if (E.fw === "n") return T("About {f} of {state}'s ballots are expected to be in this block: the ballots already in, over the turnout the model expects, already reach that much.", {f: pct(E.f), state: SN(S)});
    if (E.fw === "s") return T("About {f} of {state}'s ballots are expected to be in this block, as in the {y} survey of election offices, the share the election-night model starts from.", {f: pct(E.f), state: SN(S), y: String(S.fs[1])});
    return T("About {f} of {state}'s ballots are expected to be in this block, the election-night model's national guess, since no survey figure for the state passes its checks.", {f: pct(E.f), state: SN(S)});
  }
  function gapWords(S) {
    const mail = S.blk === "mail", G = DATA.gap;
    const start = S.g[2] === "own" ? T("This page starts from half of {state}'s own past gap, from its counted official results ({years}), as the election-night model does.", {state: SN(S), years: S.g[3].map(x => x[0]).join(", ")})
      : T("{state}'s counted results do not split the kinds of ballot, so this page starts from half of the typical state's gap, as the election-night model does.", {state: SN(S)});
    return (mail ? T("How it is worked out: the race's forecast for all ballots is split in two, the mail ballots and those cast in person, by how differently the two leaned in past official counts. In every state whose counts split them, mail ballots leaned more Democratic than ballots cast in person.")
      : T("How it is worked out: the race's forecast for all ballots is split in two, the ballots cast before Election Day and those cast on it, by how differently the two leaned in past official counts. In every state whose counts split them, ballots cast before Election Day leaned more Democratic, and the gap shrank from 2022 to 2024.")) + " " + start;
  }
  function render(el) {
    const code = el.dataset.es, S = DATA && DATA.st[code], h = Math.min(5, Math.max(2, +el.dataset.h || 2));
    if (!S) { el.innerHTML = ""; el.hidden = true; return; }
    el.hidden = false;
    live(code).then(l => {
      if (!el.isConnected || el.dataset.es !== code) return;
      const ev = fresh(code, S, l), n = countOf(S, ev), H = `h${h}`, h2 = `h${h + 1}`, night = url("../../night/us/#state=" + code);
      let o = `<div class="eshd"><${H} id="es-h-${esc(code)}">${esc(T("The ballots already in, as forecast"))}</${H}><span class="tag analysis">${esc(T("Analysis"))}</span></div>`;
      if (!ev || !ev.head) {
        o += `<p>${esc(ev && ev.say ? ev.say : T("No count of ballots cast before Election Day in {state} is read here.", {state: SN(S)}))}</p>`;
        o += `<p class="essub">${esc(T("Where a state posts its own count of the ballots already in, this part of the page estimates how they probably lean, from the race's forecast and past official counts. With no count, there is no estimate here."))}</p>`;
        o += `<p class="essub"><a href="${esc(night)}">${esc(T("Ballots cast so far, state by state, on Election Night"))}</a></p>`;
        el.innerHTML = o; return;
      }
      o += `<p data-lv="2">${esc(T("No state releases how anyone voted before its polls close. What a state does post is how many ballots it has in hand. From that count, the race's forecast and how ballots cast early leaned in past official counts, the model estimates how the ballots already in probably lean, and what the first figures on election night will likely show."))}</p>`;
      const mail = S.blk === "mail";
      o += `<div class="esn"><b>${esc(num(n))}</b><span>${esc(mail ? T("mail ballots already in, as {pub} counts them, as of {date}.", {pub: ev.pub ? thePub(ev.pub) : SN(S), date: day(ev.head.at)}) : T("ballots already in, as {pub} counts them, as of {date}.", {pub: ev.pub ? thePub(ev.pub) : SN(S), date: day(ev.head.at)}))}</span></div>`;
      o += `<p class="essub"><span class="tag fact">${esc(T("Fact"))}</span> <a href="${esc(night)}">${esc(T("Every figure of {state}'s count, on Election Night's Ballots cast so far", {state: SN(S)}))}</a>${ev.link ? ` &middot; <a href="${esc(ev.link[0])}" target="_blank" rel="noopener">${esc(T("{state}'s own page", {state: SN(S)}))}</a>` : ""}</p>`;
      o += `<p class="essub" data-lv="3">${esc(pastWords(S))}</p>`;
      const main = S.r.filter(r => r[2] !== "X"), rest = S.r.filter(r => r[2] === "X");
      const shown = main.length ? main : rest.slice(0, 1), others = main.length ? rest : rest.slice(1);
      if (!S.r.length) o += `<p>${esc(T("No statewide race in {state} has a forecast between one Democrat and one Republican, so there is no estimate of how these ballots lean.", {state: SN(S)}))}</p>`;
      shown.forEach(r => { o += raceHTML(S, r, n, h + 1); });
      o += otherHTML(S, others, n);
      if (S.r.length) {
        const E0 = est(S, S.r[0], n);
        o += `<div data-lv="3"><p class="esmath">${esc(gapWords(S))} ${esc(fWords(S, E0))}</p></div>`;
        o += `<ul class="eswarn"><li>${esc(T("This is an estimate, not a count, and not a call: no state releases how anyone voted before its polls close, and the official count decides."))}</li>`
          + `<li data-lv="2">${esc(T("It has no track record of its own. Its least sure part is the starting gap: half of a state's 2022 gap missed its 2024 gap by about {own} on the log-odds scale (about {pts} points of share in an even race), and half of the typical state's by {typ}. The likely ranges include that.", {own: one(DATA.gap.own), pts: num(Math.round(DATA.gap.own * 25)), typ: one(DATA.gap.typ)}))}</li>`
          + `<li data-lv="2">${esc(mail ? T("Mail ballots still to come are taken to lean like those already in.") : T("Ballots still to come before Election Day are taken to lean like those already in."))}</li>`
          + `<li>${esc(T("The voters' registered party is never used in this estimate."))}</li></ul>`;
        o += `<details data-lv="6"><summary>${esc(T("The model runs behind this"))}</summary><ul class="esruns">${[...new Set(S.r.map(r => r[9]))].map(i => DATA.runs[i]).filter(Boolean).map(r => `<li translate="no">${esc(r[0])}${r[2] ? " &middot; " + esc(r[2]) : ""}</li>`).join("")}${DATA.night ? `<li translate="no">${esc(DATA.night)} &middot; ${esc(T("the election-night model's starting gaps and mixes"))}</li>` : ""}</ul></details>`;
      }
      o += partyHTML(ev, h + 1);
      el.innerHTML = o;
      if (LOC && I18.dom) I18.dom(el);
    });
  }
  function mount(el) {
    if (!el) return;
    if (!el.classList.contains("es")) el.classList.add("es");
    if (!document.getElementById("es-css")) { const s = document.createElement("style"); s.id = "es-css"; s.textContent = ".es{margin:22px 0 0;min-width:0;max-width:100%;border:1px solid var(--line);border-radius:16px;background:var(--surface);padding:14px 16px 16px}\n.es *{box-sizing:border-box}\n.es .eshd{display:flex;gap:8px 12px;align-items:center;flex-wrap:wrap;margin:0}\n.es .eshd>:first-child{margin:0;font-family:var(--serif);font-weight:400;font-size:clamp(22px,2.6vw,28px);line-height:1.15;text-transform:none;letter-spacing:0;color:var(--ink)}\n.es p{margin:8px 0 0;max-width:80ch;line-height:1.5;font-size:15px}\n.es .essub{color:var(--muted);font-size:14px}\n.es a{color:var(--accent-ink,var(--accent))}\n.es a:focus-visible,.es summary:focus-visible{outline:3px solid var(--accent);outline-offset:2px}\n.es .esn{display:flex;flex-wrap:wrap;align-items:baseline;gap:4px 12px;margin:12px 0 0}\n.es .esn b{font-family:var(--serif);font-weight:400;font-size:clamp(30px,4.4vw,42px);line-height:1;font-variant-numeric:tabular-nums}\n.es .esn span{font-size:15px;max-width:62ch;line-height:1.45}\n.es .esr{border-top:1px solid var(--line);margin:16px 0 0;padding:12px 0 0}\n.es .esr>:first-child{margin:0;font:700 16px/1.35 var(--sans);text-transform:none;letter-spacing:0;color:var(--ink)}\n.es .esone{font-size:15.5px}\n.es .esfig{margin:10px 0 0;padding:0;display:grid;grid-template-columns:minmax(0,1fr) auto;gap:4px 14px;font-size:14px;max-width:560px}\n.es .esfig dt{color:var(--ink)}.es .esfig dd{margin:0;text-align:right;font-variant-numeric:tabular-nums;max-width:10.5em}\n.es .esfig dd b{font-weight:700}.es .esfig dd small{display:block;color:var(--muted);font-size:12.5px;line-height:1.3}\n.es svg.espic{display:block;width:100%;max-width:560px;height:auto;margin:10px 0 0;color:var(--ink);overflow:visible}\n.es .espic text{font:11.5px var(--sans);fill:var(--muted)}\n.es .espic .lb{fill:var(--ink)}\n.es .espic .bar{fill:currentColor;opacity:.16}\n.es .espic .dot{fill:currentColor}\n.es .espic .even{stroke:var(--line-strong);stroke-dasharray:3 3}\n.es .espic .axis{stroke:var(--line-strong)}\n.es .espic .go{stroke:var(--accent);stroke-width:2.5;fill:none}\n.es .espic .goh{fill:var(--accent)}\n.es .escap{font-size:12.5px;color:var(--muted);margin:4px 0 0;max-width:80ch}\n.es .eswarn{margin:14px 0 0;padding:10px 14px 10px 30px;border:1px solid var(--line);border-left:5px solid var(--brass,var(--accent));border-radius:12px;background:var(--bg);font-size:13.5px;line-height:1.5;max-width:96ch}\n.es .eswarn li+li{margin-top:4px}\n.es details{margin:14px 0 0;border:1px solid var(--line);border-radius:12px;background:var(--bg);padding:0 12px}\n.es summary{cursor:pointer;min-height:44px;display:flex;align-items:center;font:600 14.5px var(--sans)}\n.es details[open]>summary{border-bottom:1px solid var(--line)}\n.es .estw{overflow-x:auto;max-width:100%}\n.es table{border-collapse:collapse;width:100%;font-size:13.5px;margin:8px 0}\n.es th,.es td{padding:6px 10px;border-top:1px solid var(--line);text-align:left;vertical-align:baseline}\n.es thead th{font-size:12px;color:var(--muted);font-weight:700;border-top:0;vertical-align:bottom}\n.es td.n,.es th.n{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}\n.es tbody th{font-weight:600}\n.es tr[data-p] th{border-left:5px solid var(--pc,var(--line-strong))}\n.es .esparty{margin:18px 0 0}\n.es .esparty>:first-child{margin:0;font:700 15px var(--sans);text-transform:none;letter-spacing:0;color:var(--ink)}\n.es .esnote{font-size:14px;margin:8px 0 0;max-width:90ch;line-height:1.5;padding:8px 12px;border-left:4px solid var(--line-strong);background:var(--bg);border-radius:0 8px 8px 0}\n.es .esmath{font-size:13.5px;color:var(--ink)}\n.es ul.esruns{margin:6px 0 0;padding-left:20px;font-size:13px}\n.es .tag{flex:none}\n.es [hidden]{display:none!important}"; document.head.appendChild(s); }
    const go = () => need().then(() => render(el), () => { el.innerHTML = `<p class="essub">${esc(T("The estimate of the ballots already in could not be loaded. Check your connection and open the page again."))}</p>`; });
    (LOC ? I18.ready : Promise.resolve()).then(go, go);
  }
  window.ES = {mount};
  const auto = () => document.querySelectorAll("[data-es]").forEach(mount);
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", auto); else auto();
})();
