/* Each state's forecast map and "Your ballot, as forecast" (John, 2026-10-26), one script for On The Ballot's and Election
   Night's Forecasts pages, reading the files beside it. The lines are the ballot pages' own (their map and its reader, from the maps
   folder) or, where a state has none, the Congress page's; the figures are the model's, labelled Analysis; a chance is never written as
   0 or 100 percent. A page names a box: <section data-sm="MN" data-chips="1" data-lv=""></section>. The reader's spot is used here and
   now on this device; only a copy rounded to about half a mile is kept, as on the ballot pages, until "Forget my location". */
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
  const I18P = n => LOC ? I18.place(n) : n;
  const num = n => LOC ? I18.num(n) : EN.num(n);
  const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"}[c]));
  const nm = n => `<span translate="no">${esc(n)}</span>`;
  const pc = x => x < 0.01 ? T("under 1%") : x > 0.99 ? T("over 99%") : (LOC ? I18.num(Math.round(x * 100) / 100, {style: "percent"}) : Math.round(x * 100) + "%");
  const share = v => LOC ? I18.num(v / 100, {style: "percent", maximumFractionDigits: 0}) : Math.round(v) + "%";
  const calm = () => HTML.classList.contains("calm") || HTML.dataset.motion === "reduced" || HTML.dataset.calm === "on" || matchMedia("(prefers-reduced-motion: reduce)").matches;
  const store = {get: k => { try { return localStorage.getItem(k); } catch (e) { return null; } }, set: (k, v) => { try { localStorage.setItem(k, v); } catch (e) {} },
    del: k => { try { localStorage.removeItem(k); } catch (e) {} }};
  /* the record's own map drawing (the Albers lines of the Congress page and the states' outlines) and its point-in-shape test */
  const conic = (parallels, rotLon, center, scale, tx, ty) => {
    const rad = Math.PI / 180, y0 = parallels[0] * rad, sy0 = Math.sin(y0), n = (sy0 + Math.sin(parallels[1] * rad)) / 2, c = 1 + sy0 * (2 * n - sy0), r0 = Math.sqrt(c) / n;
    const raw = (lam, phi) => { const r = Math.sqrt(c - 2 * n * Math.sin(phi)) / n, x = lam * n; return [r * Math.sin(x), r0 - r * Math.cos(x)]; };
    const [cx, cy] = raw(center[0] * rad, center[1] * rad), dx = tx - scale * cx, dy = ty + scale * cy;
    return (lon, lat) => { const lam = ((((lon + rotLon + 180) % 360) + 360) % 360 - 180) * rad, [x, y] = raw(lam, lat * rad); return [scale * x + dx, dy - scale * y]; };
  };
  const albersUsa = (() => {
    const k = 1300, tx = 487.5, ty = 305, E = 1e-6;
    const lower48 = conic([29.5, 45.5], 96, [-0.6, 38.7], k, tx, ty), alaska = conic([55, 65], 154, [-2, 58.5], k * .35, tx - .307 * k, ty + .201 * k), hawaii = conic([8, 18], 157, [-3, 19.9], k, tx - .205 * k, ty + .212 * k);
    // as d3 does it going forward: each part of the map accepts only points that land inside its own frame
    const inBox = (p, x0, y0, x1, y1) => p[0] >= tx + x0 * k - E && p[0] < tx + x1 * k + E && p[1] >= ty + y0 * k - E && p[1] < ty + y1 * k + E;
    return (lon, lat) => { let p = lower48(lon, lat); if (inBox(p, -.455, -.238, .455, .238)) return [p[0], p[1], 1];
      p = alaska(lon, lat); if (inBox(p, -.425, .120, -.214, .234)) return [p[0], p[1], .35];      // Alaska is drawn at 35% scale
      p = hawaii(lon, lat); if (inBox(p, -.214, .166, -.115, .234)) return [p[0], p[1], 1];
      return null; };
  })();
  const inRing = (pt, ring) => { let inside = false; for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) { const [xi, yi] = ring[i], [xj, yj] = ring[j]; if ((yi > pt[1]) !== (yj > pt[1]) && pt[0] < (xj - xi) * (pt[1] - yi) / (yj - yi) + xi) inside = !inside; } return inside; };
  const inShape = (pt, rings) => rings.reduce((n, r) => n + (inRing(pt, r) ? 1 : 0), 0) % 2 === 1;
  const pathRings = d => d.split("M").filter(Boolean).map(seg => seg.replace(/Z$/, "").split("L").map(p => p.split(",").map(Number)));
  const decodeRing = (ring, q) => { let x = 0, y = 0; const pts = []; for (let i = 0; i < ring.length; i += 2) { x += ring[i]; y += ring[i + 1]; pts.push([x / q, y / q]); } return pts; };

  /* the typed address, borrowed whole from the ballot pages: the words go from this device straight to the Census Bureau's address finder */
/* ---------- finding a typed address (John, 2026-10-16): for a reader who would rather not share their location, the U.S. Census Bureau's
   free address finder (its Geocoder, onelineaddress, benchmark Public_AR_Current). The typed words go from this browser straight to the
   Census Bureau, and only when the reader presses Look up (never as they type), with no referrer; this site never sees them. The page reads
   back the coordinates and the matched address line (shown so the reader can check it), hands the coordinates to the page's own "use my
   location" path as a device location would be, and keeps neither the words nor the answer: nothing in storage, nothing in the address bar,
   the box emptied once a place is found. The Geocoder sends no CORS header (a fetch is refused; checked 2026-10-16), so it is asked by its
   JSONP form: a script tag, removed as soon as it answers or gives up. A post office box or a rural route says nothing of where a home
   stands and is not sent at all. The state ballot pages borrow this part whole (BALLOT_BORROWED["ADDRFIND"]). ---------- */
const ADDR = (() => {
  const NM = {}; "AL Alabama|AK Alaska|AZ Arizona|AR Arkansas|CA California|CO Colorado|CT Connecticut|DE Delaware|FL Florida|GA Georgia|HI Hawaii|ID Idaho|IL Illinois|IN Indiana|IA Iowa|KS Kansas|KY Kentucky|LA Louisiana|ME Maine|MD Maryland|MA Massachusetts|MI Michigan|MN Minnesota|MS Mississippi|MO Missouri|MT Montana|NE Nebraska|NV Nevada|NH New Hampshire|NJ New Jersey|NM New Mexico|NY New York|NC North Carolina|ND North Dakota|OH Ohio|OK Oklahoma|OR Oregon|PA Pennsylvania|RI Rhode Island|SC South Carolina|SD South Dakota|TN Tennessee|TX Texas|UT Utah|VT Vermont|VA Virginia|WA Washington|WV West Virginia|WI Wisconsin|WY Wyoming".split("|").forEach(s => { NM[s.slice(0, 2)] = s.slice(3); });
  const OTHER = () => TH("You can also use your location, or pick by hand.");      /* every message is whole, in the reader's language (T, TH: shell_src/i18npage.js) */
  const PO = /\b(p\.?\s*o\.?\s*box|post\s*office\s*box|pob\s*\d)/i, RR = /\b(r\.?\s*r\.?|rural\s*route|h\.?\s*c\.?|highway\s*contract|star\s*route)\s*#?\s*\d/i;
  const html = id => `<form class="addrf" id="${id}" novalidate><label for="${id}q">${TH("Or type your address: house number and street, then city and state, or ZIP")}</label><div class="addrrow"><input type="text" id="${id}q" maxlength="100" autocomplete="off" spellcheck="false" enterkeyhint="search" placeholder="${esc(T("House number and street, city and state, or ZIP"))}" aria-describedby="${id}n"><button type="submit" class="locbtn">${TH("Look up")}</button></div><p class="addrn" id="${id}n">${TH("Your address goes straight from this device to the U.S. Census Bureau’s address finder to find where it is; <0>the Bureau’s privacy policy</0> covers what it receives. The Civic Archive never sees it or keeps it.", {0: s => `<a href="https://www.census.gov/about/policies/privacy.html" target="_blank" rel="noopener noreferrer">${s}</a>`})}</p><div class="addrs" role="status" aria-live="polite"></div></form>`;
  const ask = text => new Promise((res, rej) => {      // -> the matches [{lon, lat, st, line}]; or "timeout", "down"
    const cb = "__tcaAddr" + Math.random().toString(36).slice(2), s = document.createElement("script"); let done = false;
    const end = late => { done = true; clearTimeout(t); s.remove(); if (late) window[cb] = () => {}; else delete window[cb]; };      // a late answer after a time-out lands nowhere
    const t = setTimeout(() => { if (!done) { end(1); rej("timeout"); } }, 15000);
    window[cb] = j => { if (done) return; end(); try { const seen = new Set();
      res(((j && j.result && j.result.addressMatches) || []).map(m => ({lon: +m.coordinates.x, lat: +m.coordinates.y, st: String((m.addressComponents || {}).state || "").toUpperCase(), line: String(m.matchedAddress || "")}))
        .filter(m => isFinite(m.lon) && isFinite(m.lat) && !seen.has(m.line) && seen.add(m.line))); } catch (e) { rej("down"); } };
    s.onerror = () => { if (!done) { end(1); rej("down"); } };
    s.referrerPolicy = "no-referrer"; s.async = true;
    s.src = "https://geocoding.geo.census.gov/geocoder/locations/onelineaddress?address=" + encodeURIComponent(text) + "&benchmark=Public_AR_Current&format=jsonp&callback=" + cb;
    document.head.appendChild(s);
  });
  const EXTRA = {DC: "the District of Columbia", PR: "Puerto Rico", GU: "Guam", VI: "the U.S. Virgin Islands", AS: "American Samoa", MP: "the Northern Mariana Islands"};
  /* a single match is used without asking only when it agrees with what was typed: the same house number, every direction word typed
     (N, South...) in its street, its street's name words in the typed words, and a state or a ZIP code typed (the finder otherwise
     guesses: "200 N Spring St" alone comes back in Georgia, and with the city as "200 S Spring St") */
  const DIRS = {NORTH: "N", SOUTH: "S", EAST: "E", WEST: "W", NORTHEAST: "NE", NORTHWEST: "NW", SOUTHEAST: "SE", SOUTHWEST: "SW", N: "N", S: "S", E: "E", W: "W", NE: "NE", NW: "NW", SE: "SE", SW: "SW"};
  const SUFFIX = new Set("ST STREET AVE AVENUE RD ROAD DR DRIVE BLVD LN LANE CT PL WAY HWY PKWY CIR TER TRL APT UNIT STE".split(" "));
  const words = s => String(s).toUpperCase().replace(/[^A-Z0-9 ]+/g, " ").split(/\s+/).filter(Boolean);
  const num = s => { const x = String(s).trim().match(/^\d[\d-]*/); return x ? x[0].replace(/-/g, "") : ""; };
  const hasPlace = t => { const rest = t.replace(/^\s*\d[\d-]*/, ""), w = new Set(words(rest)), low = rest.toLowerCase();
    return /\b\d{5}\b/.test(rest) || Object.keys(NM).some(k => w.has(k) || low.includes(NM[k].toLowerCase())) || Object.keys(EXTRA).some(k => w.has(k)) || /district of columbia|puerto rico/.test(low); };
  const doubt = (t, m) => {
    const a = num(t), b = num(m.line); if (a && b && a !== b) return T("The house number is not the one you typed.");
    const typed = new Set(words(t)), mine = words(t.split(",")[0]).slice(1).map(w => DIRS[w]).filter(Boolean), theirs = words(m.line.split(",")[0]).slice(1);
    if (mine.some(d => !theirs.some(w => DIRS[w] === d)) || theirs.some(w => w.length > 2 && !DIRS[w] && !SUFFIX.has(w) && !/^\d/.test(w) && !typed.has(w))) return T("The street is not quite the one you typed.");
    if (!hasPlace(t)) return T("You did not give a state or a ZIP code, so it may be the same street somewhere else.");
    return ""; };
  /* o.here: this page's state ("" on the Congress page, which takes any state); o.pages: the states with a ballot page of their own;
     o.start(): a new lookup begins (the page clears what an earlier one said); o.out(): the address is outside the fifty states;
     o.use(match): the page's own location path */
  function wire(form, o){
    if (!form) return; const q = form.querySelector("input"), b = form.querySelector("button"), out = form.querySelector(".addrs"); let busy = false;
    const say = h => { out.innerHTML = h; };
    const take = m => { q.value = ""; say("");      // the typed words go as soon as a place is chosen; only the place is used, and only here and now
      const seen = TH("Matched by the Census Bureau: <0>{line}</0>. Not yours? Check the number and street and look it up again.", {line: m.line, 0: s => `<b translate="no">${s}</b>`});
      if (!NM[m.st]) { say(`${seen} ${m.st === "DC" ? TH("That address is in the District of Columbia. These pages cover the fifty states’ contests, so the race for the District’s delegate to the House is not here.")
        : TH("That address is in {place, select, PR {Puerto Rico} GU {Guam} VI {the U.S. Virgin Islands} AS {American Samoa} MP {the Northern Mariana Islands} other {a place outside the fifty states}}. These pages cover the fifty states’ contests, so its contest for the House is not here.", {place: m.st})}`); if (o.out) o.out(); return; }
      if (o.here && m.st !== o.here) { const own = (o.pages || []).includes(m.st), st = I18.place(NM[m.st]);
        say(`${seen} ${TH("That address is in {state}, not {here}.", {state: st, here: I18.place(NM[o.here] || o.here)})} ${own ? TH("<0>Open {state}’s ballot page</0> and look it up there.", {state: st, 0: s => `<a href="../${m.st.toLowerCase()}/#yours">${s}</a>`})
          : TH("{state} has no state ballot page here; <0>see its races for Congress</0>.", {state: st, 0: s => `<a href="../us/#state=${m.st}">${s}</a>`})}`); return; }
      say(seen); Promise.resolve(o.use(m)).catch(() => {}); };
    const pick = (ms, lead) => { say(`<p>${lead}</p><ul class="addrpick">${ms.slice(0, 8).map((m, i) => `<li><button type="button" data-i="${i}">${ms.length === 1 ? TH("Yes, use {line}", {line: RAW(`<span translate="no">${esc(m.line)}</span>`)}) : `<span translate="no">${esc(m.line)}</span>`}</button></li>`).join("")}</ul>${ms.length === 1 ? `<p>${TH("If it is not, check the address, add the city and state or the ZIP code, and look it up again.")}</p>` : ""}`);
      out.querySelector(".addrpick").addEventListener("click", ev => { const x = ev.target.closest("button[data-i]"); if (x) take(ms[+x.dataset.i]); }); };
    form.addEventListener("submit", e => { e.preventDefault(); if (busy) return;      // the button stays enabled (and keeps the keyboard focus); a second press while asking does nothing
      if (o.start) o.start();
      const text = q.value.replace(/\s+/g, " ").trim();
      if (!text) { say(TH("Type a street address first: the house number and street, then the city and state, or the ZIP code.")); q.focus(); return; }
      if (text.length > 100) { say(`${TH("The address finder takes at most 100 characters, so it was not sent. Shorten it: the house number and street, then the city and state, or the ZIP code.")} ${OTHER()}`); return; }
      if (/[<>{}\[\]\\^`|]/.test(text)) { say(`${TH("An address needs only letters, numbers and ordinary punctuation (commas, periods, hyphens, apostrophes and #), so it was not sent. Take out the other marks and look it up again.")} ${OTHER()}`); return; }
      if (PO.test(text)) { say(`${TH("A post office box does not say where you live, so it cannot place you, and it was not sent. Type the street address of your home.")} ${OTHER()}`); return; }
      if (RR.test(text)) { say(`${TH("A rural route address does not say where the house stands, so the address finder cannot place it, and it was not sent. Try the street address your home has for 911 calls (your county can tell you it).")} ${OTHER()}`); return; }
      busy = true; b.setAttribute("aria-busy", "true"); say(TH("Asking the Census Bureau’s address finder…"));
      const done = () => { busy = false; b.removeAttribute("aria-busy"); };
      ask(text).then(ms => { done();
        if (!ms.length) { say(`${TH("The Census Bureau’s address finder found no match. Check the house number and street, and add the city and state or the ZIP code; a new street can be missing from its files.")} ${OTHER()}`); return; }
        if (ms.length === 1) { const why = doubt(text, ms[0]); if (why) pick(ms, `${TH("The Census Bureau’s address finder matched <0>{line}</0>.", {line: ms[0].line, 0: s => `<b translate="no">${s}</b>`})} ${esc(why)} ${TH("Is this your address?")}`); else take(ms[0]); return; }
        if (o.here) ms.sort((x, y) => (y.st === o.here) - (x.st === o.here));      // this page's own state first
        pick(ms, TH("The Census Bureau’s address finder found {n, plural, one {# address} other {# addresses}} that could be yours. Which one is it?", {n: ms.length}));
      }, why => { done();
        say(`${why === "timeout" ? TH("The Census Bureau’s address finder did not answer in time. Try again in a minute.") : TH("The Census Bureau’s address finder could not be reached just now. Try again later.")} ${OTHER()}`); });
    });
  }
  return {html, wire, clear: () => document.querySelectorAll(".addrf").forEach(f => { f.querySelector("input").value = ""; f.querySelector(".addrs").innerHTML = ""; })};
})();


  const LVS = ["federal", "statewide", "legislature", "court", "county", "soil_water", "city", "township", "school", "hospital", "other"];
  const LVW = {federal: N_("Congress"), statewide: N_("Statewide offices"), legislature: N_("The Legislature"), court: N_("Judges"), county: N_("County offices"),
    soil_water: N_("Soil and water"), city: N_("Cities"), township: N_("Townships"), school: N_("School districts"), hospital: N_("Hospital districts"), other: N_("Other districts")};
  const KW = {state: N_("the whole state"), cd: N_("U.S. House districts"), senate: N_("State Senate districts"), house: N_("State House districts"), county: N_("counties"),
    com: N_("county board districts"), park: N_("park districts"), swcd: N_("soil and water districts"), mcd: N_("cities and townships"), ward: N_("wards"),
    school: N_("school districts"), hospital: N_("hospital districts"), judicial: N_("judicial districts")};
  const PW = {D: N_("Democratic"), R: N_("Republican"), I: N_("Independent or other")};
  const PIN = `<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="11" r="3"/><path d="M12 21s-7-6.2-7-11a7 7 0 0 1 14 0c0 4.8-7 11-7 11z"/></svg>`;
  const PIN_SVG = `<svg viewBox="0 0 26 34" aria-hidden="true"><path d="M13 33C13 33 2 20.6 2 12.4 2 6.1 6.9 1 13 1s11 5.1 11 11.4C24 20.6 13 33 13 33z"/><circle cx="13" cy="12.2" r="4.3"/></svg>`;
  let IDX = null, DIST = null, CUR = null, SPOT = null;
  const url = rel => new URL(rel, BASE).href;
  const getJSON = u => fetch(u).then(r => r.ok ? r.json() : Promise.reject(new Error(String(r.status))));
  const needIdx = () => IDX ? Promise.resolve(IDX) : getJSON(url("data/sm/index.json?v=" + DV)).then(d => (IDX = d));
  const needDist = () => DIST ? Promise.resolve(DIST) : getJSON(url(IDX.dist)).then(d => (DIST = d), () => (DIST = {q: 50, states: {}, failed: true}));
  const stName = c => I18P((IDX && IDX.names[c]) || c);
  const addScript = src => new Promise((ok, no) => { const s = document.createElement("script"); s.src = src; s.onload = ok; s.onerror = () => no(new Error(src)); document.head.appendChild(s); });
  let kitP = null, readerBase = "";
  const needKit = geo => { if (readerBase !== geo.base) { readerBase = geo.base; kitP = addScript(geo.base + "reader.js?v=" + geo.v).then(() => window.BallotMap ? null : addScript(url(IDX.kit))); }
    return kitP.catch(e => { readerBase = ""; throw e; }); };

  /* ---------- the races ---------- */
  function rows(D) {
    return D.r.map((a, n) => { const g = a[1] || "", i = g.indexOf(":");
      return {id: a[0], g, kind: i > 0 ? g.slice(0, i) : "", gid: i > 0 ? g.slice(i + 1) : "", n, lv: LVS[a[2]] || "other", o: D.o[a[3]], title: a[4] || D.o[a[3]], where: D.w[a[5]] || "", pt: a[6], k: a[7], seats: a[8] || 1, link: a[9], c: a[10] || []}; });
  }
  const linkOf = (r, code) => r.link === 1 ? url(`../us/#race=${r.id}&chart=open`) : r.link === 2 ? url(`../${code.toLowerCase()}/#race=${r.id}&chart=open`) : r.link === 3 ? url(`../../night/forecasts/#race=${r.id}`) : "";
  /* how sure: the favourite's chance (for several seats, the chance of the last of the expected winners) */
  function tier(r) {
    if (r.k === "u") return {t: "u", p: r.pt ? (r.c[0] && r.c[0][1]) || "I" : "N"};
    if (r.k === "g") return {t: "g", p: ""};
    if (r.k === "e") return {t: "tu", p: "N"};
    const last = r.c[Math.min(r.seats, r.c.length) - 1] || r.c[0], ch = last ? last[2] : 0;
    return {t: ch >= .8 ? "lk" : ch >= .6 ? "ln" : "tu", p: r.pt ? (r.c[0][1] || "I") : "N", ch};
  }
  const TIERW = {lk: N_("Likely (80% or more)"), ln: N_("Leaning (60% to 80%)"), tu: N_("Toss-up (under 60%)"), u: N_("One name for each seat: no forecast needed"), g: N_("No forecast yet")};
  /* a race in words: what the model says, or why it says nothing */
  function raceWords(r, code) {
    const go = linkOf(r, code), link = go ? ` <a href="${esc(go)}">${esc(r.link === 3 ? T("See this race's forecast") : T("Open the race's chart"))}</a>` : "";
    if (r.k === "u") return `<p>${TH("One name for each seat: {names}. No forecast is needed.", {names: RAW(r.c.map(c => nm(c[0])).join(", "))})}</p>`;
    if (r.k === "g") return `<p>${esc(T("No forecast yet."))}</p>`;
    if (r.k === "e") return `<p><span class="tag analysis">${esc(T("Analysis"))}</span> ${esc(T("Even: the record gives no reason to favour any candidate here."))}${link}</p>`;
    if (r.seats > 1) return `<p><span class="tag analysis">${esc(T("Analysis"))}</span> ${TH("{n} seats. The highest chances of a seat: {list}.", {n: r.seats, list: RAW(r.c.slice(0, r.seats).map(c => `${nm(c[0])} ${esc(pc(c[2]))}`).join(", "))})}${link}</p>`;
    const a = r.c[0], b = r.c[1];
    return `<p><span class="tag analysis">${esc(T("Analysis"))}</span> ${TH("The model favours {name}{party, select, none {} other { ({party})}}: {chance} chance, likely {lo} to {hi} of the vote.", {name: RAW(nm(a[0])), party: r.pt && a[1] ? T(PW[a[1]] || PW.I) : "none", chance: pc(a[2]), lo: share(a[3]), hi: share(a[4])})}`
      + (b ? ` ${TH("Then {name}: {chance}.", {name: RAW(nm(b[0])), chance: pc(b[2])})}` : "") + `${link}</p>`;
  }
  const raceHead = r => `<h5>${esc(r.title)}${r.where && r.lv !== "legislature" && r.lv !== "federal" && r.lv !== "statewide" ? ` <small>${esc(r.where)}</small>` : ""}</h5>`;

  /* ---------- the layers: a level's races, office by office, each office one way of shading the map ---------- */
  function groups(S, lv) {
    const by = new Map();
    S.R.forEach(r => { if (r.lv !== lv || !r.kind || !S.kinds.has(r.kind)) return; const key = r.kind + "|" + r.o; if (!by.has(key)) by.set(key, {key, kind: r.kind, o: r.o, list: [], n: 0}); const G = by.get(key); G.list.push(r); if (r.k === "f" || r.k === "e") G.n++; });
    return [...by.values()].filter(G => G.n || G.list.some(r => r.k === "u")).sort((a, b) => (b.kind === "cd") - (a.kind === "cd") || b.n - a.n || a.o.localeCompare(b.o));
  }
  function levels(S) { return LVS.filter(lv => groups(S, lv).length); }
  const defaultLevel = S => { const ls = levels(S), has = lv => groups(S, lv).some(G => G.n);      /* a level with forecasts first: a state whose House races have none (new lines) opens on its Senate or statewide races */
    return ls.includes("federal") && groups(S, "federal").some(G => G.kind === "cd" && G.n) ? "federal" : ls.includes("legislature") && has("legislature") ? "legislature" : ls.find(has) || ls[0] || ""; };

  /* ---------- the fills: party colours for party data only; the site's neutral tone where a race is not partisan; patterns as well as colour ---------- */
  function palette() {
    const cs = getComputedStyle(HTML), V = n => cs.getPropertyValue(n).trim();
    return {D: V("--pD") || "#2b59c3", R: V("--pR") || "#c8423a", I: V("--pI") || "#6E62A8", N: V("--n1") || V("--accent") || "#2F6B5E", grey: V("--line-strong") || "#c3c5bf",
      bg: V("--bg") || "#f5f5f2", surface: V("--surface") || "#fff", ink: V("--ink") || "#111"};
  }
  const rgba = (c, a) => { let m = /^#([0-9a-f]{6})$/i.exec(c); if (m) { const n = parseInt(m[1], 16); return `rgba(${n >> 16},${(n >> 8) & 255},${n & 255},${a})`; }
    m = /^#([0-9a-f]{3})$/i.exec(c); if (m) return rgba("#" + m[1].split("").map(x => x + x).join(""), a); m = /rgba?\(([^)]+)\)/.exec(c); if (m) { const p = m[1].split(/[ ,/]+/); return `rgba(${p[0]},${p[1]},${p[2]},${a})`; } return c; };
  function canvasFill(kit, P, f) {
    const c = P[f.p] || P.N;
    if (f.t === "lk") return c;
    if (f.t === "ln") return kit.pattern(c, "hatch", rgba(c, .32));
    if (f.t === "tu") return kit.pattern(c, "cross", P.surface);
    if (f.t === "u") return kit.pattern(c, "dots", rgba(c, .18));
    return kit.pattern(P.grey, "back", P.bg);
  }
  const PV = {D: "var(--pD)", R: "var(--pR)", I: "var(--pI)", N: "var(--n1, var(--accent))", "": "var(--line-strong)"};
  function svgDefs(id, u) {
    const w = u * 7, p = (k, P) => {
      const c = PV[P];
      if (k === "ln") return `<pattern id="${id}-ln-${P}" width="${w}" height="${w}" patternUnits="userSpaceOnUse" patternTransform="rotate(45)"><rect width="${w}" height="${w}" fill="${c}" fill-opacity=".3"/><rect width="${w / 2}" height="${w}" fill="${c}"/></pattern>`;
      if (k === "tu") return `<pattern id="${id}-tu-${P}" width="${w}" height="${w}" patternUnits="userSpaceOnUse"><rect width="${w}" height="${w}" fill="var(--surface)"/><rect x="0" y="${w * .45}" width="${w}" height="${w * .1 + u}" fill="${c}"/><rect x="${w * .45}" y="0" width="${w * .1 + u}" height="${w}" fill="${c}"/></pattern>`;
      return `<pattern id="${id}-u-${P}" width="${w}" height="${w}" patternUnits="userSpaceOnUse"><rect width="${w}" height="${w}" fill="${c}" fill-opacity=".18"/><circle cx="${w / 2}" cy="${w / 2}" r="${w * .2}" fill="${c}"/></pattern>`;
    };
    let o = "<defs>";
    ["D", "R", "I", "N"].forEach(P => { o += p("ln", P) + p("tu", P) + p("u", P); });
    return o + `<pattern id="${id}-g" width="${w}" height="${w}" patternUnits="userSpaceOnUse" patternTransform="rotate(-45)"><rect width="${w}" height="${w}" fill="var(--line)"/><rect width="${w * .3}" height="${w}" fill="var(--line-strong)"/></pattern></defs>`;
  }
  const svgFill = (f, id) => f.t === "lk" ? PV[f.p] || PV.N : f.t === "g" ? `url(#${id}-g)` : `url(#${id}-${f.t}-${f.p || "N"})`;
  function legend(G) {
    const nonp = G && G.list.every(r => !r.pt), id = "smlg", P = nonp ? "N" : "D";
    const sw = t => `<svg viewBox="0 0 18 18" aria-hidden="true">${t === "lk" ? (nonp ? `<rect width="18" height="18" rx="3" fill="${PV.N}"/>` : `<rect width="9" height="18" fill="${PV.D}"/><rect x="9" width="9" height="18" fill="${PV.R}"/>`)
      : `<rect width="18" height="18" rx="3" fill="${svgFill({t, p: P}, id)}" stroke="var(--line-strong)"/>`}</svg>`;
    return `<svg width="0" height="0" style="position:absolute" aria-hidden="true">${svgDefs(id, 18 / 7 / 1.6)}</svg>` + ["lk", "ln", "tu", "u", "g"].map(t => `<span>${sw(t)}${esc(T(TIERW[t]))}</span>`).join("")
      + `<span>${esc(nonp ? T("Nonpartisan races: one neutral colour, the patterns say how sure") : T("Party colours: Democratic, Republican"))}</span>`;
  }

  /* ---------- the box ---------- */
  function shell(S) {
    const lvs = levels(S), chips = S.chips && lvs.length > 1;
    return `<div class="sm"><h3 class="smh"><span>${esc(T("{state} on the map", {state: stName(S.code)}))}</span> <span class="tag analysis">${esc(T("Analysis"))}</span></h3>
      <p data-lv-max="2">${esc(T("Use your location below to see every race on your ballot in {state}, each with the model's forecast where it has one.", {state: stName(S.code)}))}</p>
      <div data-lv="3"><p class="smsub">${esc(T("Each place is shaded by the forecast for the office picked below: solid where the favourite's chance is 80% or more, striped from 60% to 80%, cross-hatched under 60%. Dotted: one name for each seat. Grey: no forecast yet. Tap a place for its race."))}</p>
      ${chips ? `<div class="smchips" role="group" aria-label="${esc(T("Which races"))}">${lvs.map(lv => `<button type="button" data-smlv="${lv}" aria-pressed="${lv === S.lv}">${esc(T(LVW[lv]))}</button>`).join("")}</div>` : ""}
      <label class="smoff"><span>${esc(T("Office"))}</span><select id="smoff"></select></label>
      <div class="smgrid" data-lv="3"><div><div id="smmapbox"></div><div class="smlegend" id="smlegend"></div><p class="smsub" id="smline"></p></div>
        <aside class="smside" id="smside" aria-live="polite"></aside></div>
      <p class="smsub" id="smnotes"></p></div></div>
      <section class="smyours" aria-labelledby="smyh"><h4 id="smyh">${esc(T("Your ballot, as forecast"))}</h4>
        <p>${esc(T("Use your location or type your address, and this device finds your districts, then lists every race on your ballot with the model's forecast. Your location stays on this device: nothing about it is sent anywhere by this page."))}</p>
        <div class="smybar"><button type="button" class="smybtn" id="smloc">${PIN}${esc(T("Use my location"))}</button><button type="button" class="smbtn" id="smforget" hidden>${esc(T("Forget my location"))}</button></div>
        ${typeof ADDR !== "undefined" ? ADDR.html("smaddr") : ""}
        <p class="smnote" id="smnote" aria-live="polite"></p><div id="smres"></div></section>`;
  }
  function fillOffices(S) {
    const sel = S.el.querySelector("#smoff"), gs = groups(S, S.lv);
    S.gs = gs;
    if (!gs.length) { sel.parentNode.hidden = true; return; }
    sel.parentNode.hidden = gs.length < 2;
    if (!gs.some(G => G.key === S.gk)) S.gk = gs[0].key;
    sel.innerHTML = gs.map(G => `<option value="${esc(G.key)}"${G.key === S.gk ? " selected" : ""}>${esc(G.o)}${gs.filter(x => x.o === G.o).length > 1 ? " (" + esc(T(KW[G.kind] || G.kind)) + ")" : ""} &middot; ${esc(T("{n, plural, one {# forecast} other {# forecasts}}", {n: G.n}))}</option>`).join("");
  }
  const curGroup = S => (S.gs || []).find(G => G.key === S.gk) || null;
  function sideHome(S) {
    const G = curGroup(S);
    if (!G) return `<p>${esc(T("No race at this level has a forecast that a map can show."))}</p>`;
    const n = G.list.length, by = {lk: 0, ln: 0, tu: 0, u: 0, g: 0}; G.list.forEach(r => by[tier(r).t]++);
    return `<h5>${esc(G.o)}</h5><p>${esc(T("{n, plural, one {# race} other {# races}}: {a} likely, {b} leaning, {c} toss-up, {d} with one name for each seat, {e} with no forecast yet.", {n, a: by.lk, b: by.ln, c: by.tu, d: by.u, e: by.g}))}</p>
      <p class="smsub">${esc(T("Point at a place, or tap one, to see its race."))}</p>`;
  }
  function pickedId(S, kind, id, name) {
    const G = curGroup(S), side = S.el.querySelector("#smside"); if (!side || !G) return;
    if (id == null) { side.innerHTML = sideHome(S); return; }
    const rs = G.list.filter(r => r.kind === kind && String(r.gid) === String(id));
    side.innerHTML = rs.length ? rs.map(r => `<div class="smr">${raceHead(r)}${raceWords(r, S.code)}</div>`).join("")
      : `<p>${esc(name ? T("{place}: no race for this office here.", {place: name}) : T("No race for this office here."))}</p>`;
  }

  /* ---------- the map: the ballot pages' own (engine A) or the Congress page's lines (engine B) ---------- */
  function drawMap(S) {
    const box = S.el.querySelector("#smmapbox"), G = curGroup(S), note = S.el.querySelector("#smnotes");
    S.el.querySelector("#smlegend").innerHTML = legend(G);
    S.el.querySelector("#smside").innerHTML = sideHome(S);
    const notes = [];
    if (S.D.changed) notes.push(      /* at every level: "Your ballot" below places the reader in a House district only on the 2026 lines */(S.D.geo && S.D.cdmap) || (!S.D.geo && S.D.cd26) ? T("{state} drew new congressional lines for 2026; the map draws the new districts, and none has a forecast yet.", {state: stName(S.code)})
      : T("{state} drew new congressional lines for 2026. The new map is not drawn here yet, so its districts are not shaded; the old lines would be the wrong districts.", {state: stName(S.code)}));
    note.textContent = notes.join(" ");
    if (!G) { box.innerHTML = ""; return; }
    if (S.D.geo) {
      if (S.map && S.mapKind === G.kind) { S.map.setLayer(G.kind); S.map.select(null); S.map.redraw(); return; }
      if (!S.map) box.innerHTML = `<div class="smzoom" role="group" aria-label="${esc(T("Zoom"))}"><button type="button" data-z="in" aria-label="${esc(T("Zoom in"))}">+</button><button type="button" data-z="out" aria-label="${esc(T("Zoom out"))}">&minus;</button><button type="button" data-z="fit" aria-label="${esc(T("Show the whole state"))}">&#10530;</button></div>
        <div class="smmap" id="smmap" tabindex="0" role="group" aria-roledescription="${esc(T("map"))}" aria-label="${esc(T("Map of {state}", {state: stName(S.code)}))}"><canvas aria-hidden="true"></canvas><div class="gtiles"></div><div class="gpin" hidden aria-hidden="true">${PIN_SVG}</div><span class="gbusy" hidden>${esc(T("Loading lines…"))}</span></div>`;
      S.mapKind = G.kind;
      if (S.map) { S.map.setLayer(G.kind); S.map.redraw(); return; }
      return needKit(S.D.geo).then(() => getJSON(S.D.geo.base + "index.json?v=" + S.D.geo.v)).then(gi => {
        if (!S.el.isConnected || CUR !== S) return;
        S.gi = gi; const el = S.el.querySelector("#smmap");
        S.map = BallotMap(el, {index: gi, base: S.D.geo.base, v: S.D.geo.v, layer: G.kind, paint: kit => paintA(S, kit),
          onPick: p => { const g = curGroup(S); if (g && g.kind === "state" && !p.cleared && !p.loading) pickedId(S, "state", S.code); else if (p.cleared) pickedId(S, null, null); else if (p.loading) S.el.querySelector("#smside").innerHTML = `<p>${esc(T("The lines for this part of the map are still loading. Tap again in a moment."))}</p>`; else pickedId(S, p.kind, p.id, p.name); },
          short: (kind, id, name) => kind === "county" ? String(name || "").replace(/ County$/, "") : ["house", "senate", "cd"].includes(kind) ? String(id) : String(name || ""),
          onView: v => { const n = S.el.querySelector("#smline"); if (n) n.textContent = v.failed && !v.detail ? T("Some of the map's lines could not be loaded. Check your connection; the map asks again as you move it.") : v.detail ? T("Close in, each precinct is shaded by its own district's race.") : T("Zoom in for the precincts' own lines."); }});
        box.querySelector(".smzoom").addEventListener("click", e => { const b = e.target.closest("button"); if (!b || !S.map) return; if (b.dataset.z === "in") S.map.zoomIn(); else if (b.dataset.z === "out") S.map.zoomOut(); else S.map.whole(); });
        if (S.mine) { S.map.setMine(S.mine); if (S.pin) S.map.setPin(S.pin); }
      }).catch(() => { box.innerHTML = `<p class="smsub">${esc(T("The map could not be loaded. Check your connection and open the page again; the list of races works without it."))}</p>`; });
    }
    return needDist().then(() => { if (S.el.isConnected && CUR === S) drawB(S, G); });
  }
  function specOf(S, G) { const m = new Map(); G.list.forEach(r => { if (!m.has(String(r.gid))) m.set(String(r.gid), tier(r)); }); return m; }
  function paintA(S, kit) {
    const G = curGroup(S); if (!G) return;
    const P = palette(), m = specOf(S, G);
    if (G.kind === "cd" && S.D.changed && !S.D.cdmap) return;      // the old lines would be the wrong districts
    if (G.kind === "state") { const f = m.get(S.code), c = f ? canvasFill(kit, P, f) : null; if (c) kit.fill(kit.detail ? "precincts" : "state", () => c, 1, null); return; }      // the whole state: close in, every precinct
    kit.fill(G.kind, id => { const f = m.get(String(id)); return f ? canvasFill(kit, P, f) : null; }, 1, P.surface);
  }
  function drawB(S, G) {
    const box = S.el.querySelector("#smmapbox"), b = IDX.box[S.code], pad = Math.max(b[2] - b[0], b[3] - b[1]) * .04;
    const vb = [b[0] - pad, b[1] - pad, b[2] - b[0] + 2 * pad, b[3] - b[1] + 2 * pad], id = "smm", u = vb[2] / 500, m = specOf(S, G);
    let o = svgDefs(id, u);
    const whole = (f, lab) => `<path data-id="${esc(G.kind === "state" ? S.code : "0")}" d="${IDX.map[S.code]}" style="fill:${f ? svgFill(f, id) : `url(#${id}-g)`}" tabindex="-1" role="button" aria-label="${esc(lab)}"/>`;
    if (G.kind === "state") { const r = G.list[0]; o += whole(tier(r), r.title); }
    else if (G.kind === "cd") {
      const raw = DIST && DIST.states[S.code];
      if (G.list.length === 1) { const r = G.list[0]; o += whole(tier(r), r.title).replace(`data-id="0"`, `data-id="${esc(r.gid)}"`); }
      else if (!raw || (S.D.changed && !S.D.cd26)) o += `<path d="${IDX.map[S.code]}" style="fill:url(#${id}-g)"/>`;      /* a state with new lines: only its 2026 lines (cd26), never the old ones */
      else { const q = DIST.q || 50;
        Object.entries(raw).forEach(([n, rings]) => { const f = m.get(String(+n)), r = G.list.find(x => String(x.gid) === String(+n));
          o += `<path data-id="${esc(String(+n))}" d="${rings.map(rg => decodeRing(rg, q)).map(pts => "M" + pts.map(p => p[0].toFixed(1) + "," + p[1].toFixed(1)).join("L") + "Z").join("")}" style="fill:${f ? svgFill(f, id) : `url(#${id}-g)`}" tabindex="-1" role="button" aria-label="${esc(r ? r.title : "")}"/>`; });
        o += `<path class="out" d="${IDX.map[S.code]}"/>`; }
    }
    if (S.pinB) o += `<circle class="pin" cx="${S.pinB[0].toFixed(2)}" cy="${S.pinB[1].toFixed(2)}" r="${(u * 5).toFixed(2)}"/>`;
    box.innerHTML = `<svg class="smsvg" viewBox="${vb.map(x => x.toFixed(1)).join(" ")}" role="group" aria-label="${esc(T("Map of {state}", {state: stName(S.code)}))}">${o}</svg>`;
    const svg = box.querySelector("svg"), ps = [...svg.querySelectorAll("path[role=button]")]; if (ps.length) ps[0].tabIndex = 0;
    const show = el => { if (!el) return; svg.querySelectorAll("path.hl").forEach(x => x.classList.remove("hl")); el.classList.add("hl"); pickedId(S, G.kind, el.dataset.id); };
    svg.addEventListener("click", e => show(e.target.closest("path[role=button]")));
    svg.addEventListener("focusin", e => show(e.target.closest("path[role=button]")));
    if (matchMedia("(hover: hover)").matches) svg.addEventListener("pointerover", e => show(e.target.closest("path[role=button]")));
    svg.addEventListener("keydown", e => { const i = ps.indexOf(document.activeElement); if (i < 0) return; let j = null;
      if (e.key === "ArrowRight" || e.key === "ArrowDown") j = Math.min(ps.length - 1, i + 1); else if (e.key === "ArrowLeft" || e.key === "ArrowUp") j = Math.max(0, i - 1);
      if (j == null) return; e.preventDefault(); ps[i].tabIndex = -1; ps[j].tabIndex = 0; ps[j].focus(); });
    S.el.querySelector("#smline").textContent = "";
  }

  /* ---------- your ballot, as forecast: the reader's districts found on this device, then every race on that ballot ---------- */
  function stateAt(lon, lat) {
    const p = albersUsa(lon, lat); if (!p) return "";
    for (const c of Object.keys(IDX.map)) { const b = IDX.box[c]; if (p[0] < b[0] || p[0] > b[2] || p[1] < b[1] || p[1] > b[3]) continue; if (inShape(p, pathRings(IDX.map[c]))) return c; }
    return "";
  }
  const BIG = ["county", "cd", "senate", "house"];      // what a rounded spot (about half a mile) can tell
  function zonesA(S, res, rough) {
    const p = res.precinct.properties || {}, kinds = new Set((S.gi.layers || []).map(L => L.kind).concat(S.gi.arc_kinds || [])), Z = {};
    const put = (k, v) => { if (!kinds.has(k) || (rough && !BIG.includes(k))) return; Z[k] = v == null ? "" : v; };
    put("county", p.county); put("senate", p.senate); put("house", p.house); put("judicial", p.judicial); put("com", p.com); put("park", p.park);
    put("swcd", p.swcd); put("hospital", p.hospital); put("ward", p.ward || []); put("mcd", res.mcd || (res.mcdMany ? null : p.mcd));
    if (res.mcdMany && !res.mcd) delete Z.mcd;
    put("school", res.school || (p.school || [])[0]); if (!res.schoolKnown && !res.school) delete Z.school;
    if (S.D.cdmap) put("cd", p.cd);
    return {Z, at: p.c, c: p.county, p: res.precinct.id, pn: p.name};
  }
  function onBallot(r, Z) {
    if (r.kind === "state") return 1;
    if (!r.kind || !(r.kind in Z)) return 0;      // 0: cannot be placed from what was found
    const v = Z[r.kind];
    return (Array.isArray(v) ? v.map(String).includes(String(r.gid)) : String(v) === String(r.gid)) ? 1 : -1;
  }
  /* Share (John, 2026-10-26: "Yes, with the warning"): as "Share my ballot" on the ballot pages, the same warning first; the link carries the
     county and the precinct's id in the map's files (with the place and school district the spot fell in), never the spot or the kept pin;
     whoever opens it sees that precinct's ballot, as forecast. Facts only, never a candidate's name */
  const SHARE_SVG = `<svg viewBox="0 0 24 24" aria-hidden="true" focusable="false"><circle cx="18" cy="5" r="3"/><circle cx="6" cy="12" r="3"/><circle cx="18" cy="19" r="3"/><path d="M8.6 13.5l6.8 4M15.4 6.5l-6.8 4"/></svg>`;
  const ELDAY = () => LOC ? I18.date("2026-11-03", {month: "long", day: "numeric"}) : "November 3";
  function shareButton(S, sh) {
    if (!sh || !sh.p) return "";
    const q = ["ballot"], add = (k, v) => { if (v) q.push(k + "=" + encodeURIComponent(v)); };
    add("c", sh.c); add("p", sh.p); add("pm", sh.pm); add("ps", sh.ps);
    const st = stName(S.code), where = sh.cn ? `${sh.cn}, ${st}` : st;
    const o = {url: location.origin + location.pathname + "#" + (S.night ? "state=" : "st=") + S.code + "&" + q.join("&"), title: T("A ballot for {where}, as forecast", {where}),
      text: T("{state}: the races on one precinct's {date} ballot, with the model's forecasts. Analysis, not a result.", {state: st, date: ELDAY()}) + " The Civic Archive",
      warn: T("This link shows the ballot for your precinct, so anyone who opens it can tell roughly where you vote. It does not carry your address or your exact location.")};
    return `<button type="button" class="tca-share smsh" data-share data-share-url="${esc(o.url)}" data-share-title="${esc(o.title)}" data-share-text="${esc(o.text)}" data-share-warn="${esc(o.warn)}">${SHARE_SVG}<span>${esc(T("Share"))}</span></button>`;
  }
  function ballotHTML(S, Z, rough, sh) {
    const on = [], unplaced = new Map();
    S.R.forEach(r => { const b = onBallot(r, Z); if (b === 1) on.push(r); else if (b === 0) unplaced.set(r.lv, (unplaced.get(r.lv) || 0) + 1); });
    on.sort((a, b) => LVS.indexOf(a.lv) - LVS.indexOf(b.lv) || a.n - b.n);      /* the ballot's own order: level by level, then as the state's list gives them */
    let o = "", lv = "";
    const nf = on.filter(r => r.k === "f" || r.k === "e").length;
    o += `<div class="smybar"><p>${esc(T("{n, plural, one {# race is} other {# races are}} on your ballot here; {f, plural, one {# has} other {# have}} a forecast.", {n: on.length, f: nf}))}</p>${shareButton(S, sh)}</div><ul class="smlist">`;
    on.forEach(r => { if (r.lv !== lv) { lv = r.lv; o += `</ul><p class="smlv">${esc(T(LVW[lv]))}</p><ul class="smlist">`; }
      const f = tier(r); o += `<li style="--c:${f.t === "g" ? PV[""] : PV[f.p] || PV.N}"><b>${esc(r.title)}</b>${r.where && !["federal", "statewide", "legislature"].includes(r.lv) ? `<small>${esc(r.where)}</small>` : ""}${raceWords(r, S.code)}</li>`; });
    o += `</ul>`;
    if (unplaced.size) o += `<p class="smsub">${esc(T("These could not be placed from {how}: {list}. The state's own ballot lookup or your county's sample ballot is the authority.", {how: rough ? T("the rounded location this device keeps") : T("your location on these lines"),
      list: [...unplaced.entries()].sort((a, b) => LVS.indexOf(a[0]) - LVS.indexOf(b[0])).map(([l, n]) => `${T(LVW[l])} (${num(n)})`).join(", ")}))}</p>`;
    return o.replace(/<ul class="smlist"><\/ul>/g, "");
  }
  /* the map's files at hand: the reader with them, the index, and the map itself once the page has drawn it */
  const mapReady = S => needKit(S.D.geo).then(() => S.gi ? null : getJSON(S.D.geo.base + "index.json?v=" + S.D.geo.v).then(gi => { S.gi = gi; })).then(() => S.map ? S.map
    : new Promise(ok => { const t = setInterval(() => { if (S.map || !S.el.isConnected) { clearInterval(t); ok(S.map || null); } }, 120); setTimeout(() => { clearInterval(t); ok(S.map || null); }, 8000); }));
  const countyName = (S, c) => ((S.gi && S.gi.counties || []).find(x => x.id === c) || {}).name || "";
  function placeHere(S, lon, lat, acc, lead, rough) {
    const note = S.el.querySelector("#smnote"), res = S.el.querySelector("#smres");
    const done = (Z, words, sh) => { res.innerHTML = ballotHTML(S, Z, rough, sh); note.textContent = words; S.el.querySelector("#smforget").hidden = false; };
    if (S.D.geo) return mapReady(S).then(map => map ? map.locate(lon, lat) : null).then(hit => {
      if (!hit) { note.textContent = T("That spot isn't inside {state} on the map.", {state: stName(S.code)}); return false; }
      const z = zonesA(S, hit, rough), sh = rough ? null : {c: z.c, p: z.p, pm: hit.mcd || "", ps: hit.school || "", cn: countyName(S, z.c)};
      S.mine = {c: z.c, p: rough ? null : z.p, at: z.at, ids: Object.assign({}, z.Z)}; S.pin = rough ? null : [lon, lat];
      if (S.map) { S.map.setMine(S.mine); S.map.setPin(S.pin); const mb = S.el.querySelector("#smmap"); if (!rough && mb && mb.offsetWidth) S.map.goTo(lon, lat, 11.5); }
      done(z.Z, `${lead} ${rough ? T("Placed from the rounded location this device keeps (about half a mile): the county and the larger districts only. Near a line the guess can be off.") : T("You are in {place}.", {place: z.pn || ""})}`, sh);
      return true;
    });
    return needDist().then(() => {
      const Z = {}, p = albersUsa(lon, lat), raw = DIST.states[S.code], house = S.R.filter(r => r.kind === "cd");
      if (house.length === 1) Z.cd = house[0].gid;
      else if (raw && (!S.D.changed || S.D.cd26) && p) { const q = DIST.q || 50; for (const [n, rings] of Object.entries(raw)) if (inShape(p, rings.map(rg => decodeRing(rg, q)))) { Z.cd = String(+n); break; } }
      S.pinB = p ? [p[0], p[1]] : null; const G = curGroup(S); if (G && !S.D.geo) drawB(S, G);
      done(Z, `${lead} ${T("This state's precinct lines are not on file here, so only its statewide races and, where the 2026 lines are on file, its U.S. House district can be placed.")}`);
      return true;
    });
  }
  /* a spot from this device or from a typed address: its state first (the reader may be in another), then the same path */
  function useSpot(lon, lat, acc, lead, st) {
    const S = CUR; if (!S) return Promise.resolve(false);
    st = st || stateAt(lon, lat);
    const note = S.el.querySelector("#smnote");
    if (!st) { note.textContent = T("That spot isn't inside one of the fifty states on the map."); return Promise.resolve(false); }
    store.set("pin", JSON.stringify({st, lat: Math.round(lat * 100) / 100, lon: Math.round(lon * 100) / 100, acc: Math.round(acc || 0)})); store.set("state", st);      // rounded: about half a mile, the same kept pin the other pages use
    if (st !== S.code) {
      if (!IDX.st[st]) { note.textContent = T("That spot is in {state}, where this view is not open yet.", {state: stName(st)}); return Promise.resolve(false); }
      SPOT = {lon, lat, acc, lead, st};      // kept in this page's memory only, for the state's own view, then dropped
      note.textContent = T("That spot is in {state}. Opening {state}…", {state: stName(st)});
      if (S.go) S.go(st);
      return Promise.resolve(true);
    }
    return placeHere(S, lon, lat, acc, lead, false).catch(() => { note.textContent = T("Couldn't load the map's lines. Check your connection and try again."); });
  }
  function forget(S) {
    ["pin", "district", "state", "ballot:mine", "ballot:kept"].forEach(k => store.del(k));
    try { Object.keys(localStorage).filter(k => k.startsWith("ballot:arr:") || /^(ballot|sld):[a-z]{2}$/.test(k)).forEach(k => store.del(k)); } catch (e) {}      // the same records the ballot pages forget: one tap forgets everywhere
    try { navigator.serviceWorker.getRegistrations().then(rs => rs.forEach(r => { if (/\/ballot\/kept\/$/.test(r.scope)) r.unregister(); })).catch(() => {}); } catch (e) {}
    SPOT = null; S.mine = null; S.pin = null; S.pinB = null; if (S.map) { S.map.setMine(null); S.map.setPin(null); }
    const G = curGroup(S); if (G && !S.D.geo && DIST) drawB(S, G);
    if (typeof ADDR !== "undefined") ADDR.clear();
    S.el.querySelector("#smres").innerHTML = ""; S.el.querySelector("#smforget").hidden = true;
    S.el.querySelector("#smnote").textContent = T("Forgotten. Your location, your choices and any ballot kept on this device are no longer kept.");
  }
  function openShared(S, q) {
    const ok = v => /^[\w.|:-]{1,40}$/.test(v), c = q.get("c") || "", p = q.get("p") || "", pm = q.get("pm") || "", ps = q.get("ps") || "";
    const note = S.el.querySelector("#smnote"), res = S.el.querySelector("#smres");
    if (!S.D.geo || !ok(c) || !ok(p)) return false;
    note.textContent = T("Finding the precinct this ballot was shared for…");
    mapReady(S).then(map => { const meta = map && (S.gi.counties || []).find(x => x.id === c); return meta ? map.load(meta.file) : null; }).then(f => {
      const g = f && f.objects.precincts.geometries.find(x => x.id === p);
      if (!g) { note.textContent = T("The precinct this ballot was shared for is not on this map now. Use your location or type your address to see your own."); return; }
      const z = zonesA(S, {precinct: g, mcd: ok(pm) ? pm : null, school: ok(ps) ? ps : null, schoolKnown: true}, false), cn = countyName(S, c);
      S.mine = {c: z.c, p: z.p, at: z.at, ids: Object.assign({}, z.Z)};
      if (S.map) { S.map.setMine(S.mine); const mb = S.el.querySelector("#smmap"); if (mb && mb.offsetWidth && g.bbox) S.map.fitBox(g.bbox, 14, 10); }
      res.innerHTML = ballotHTML(S, z.Z, false, {c, p, pm: ok(pm) ? pm : "", ps: ok(ps) ? ps : "", cn});
      note.textContent = T("The forecasts for a ballot someone shared with you: {place}, {county}. Use your location or type your address to see your own; this one is not kept on this device.", {place: z.pn || "", county: cn});
    }).catch(() => { note.textContent = T("Couldn't load the map's lines. Check your connection and try again."); });
    return true;
  }
  function wireYours(S) {
    const note = S.el.querySelector("#smnote");
    S.el.querySelector("#smloc").addEventListener("click", () => {
      if (!navigator.geolocation) { note.textContent = T("Location isn't available in this browser. Type your address instead."); return; }
      note.textContent = T("Finding your districts…");
      navigator.geolocation.getCurrentPosition(pos => useSpot(pos.coords.longitude, pos.coords.latitude, pos.coords.accuracy, T("Worked out on this device; your location never leaves it.")),
        () => { note.textContent = T("Location wasn't shared. Type your address instead."); }, {enableHighAccuracy: true, timeout: 15000, maximumAge: 0});
    });
    S.el.querySelector("#smforget").addEventListener("click", () => forget(S));
    if (typeof ADDR !== "undefined") ADDR.wire(S.el.querySelector("#smaddr"), {here: "", pages: [], start: () => { note.textContent = ""; },
      use: m => { note.textContent = T("Finding your districts…"); return useSpot(m.lon, m.lat, 0, T("Found from the address you typed (only the Census Bureau saw it); the rest was worked out on this device."), m.st); }});
    let pj = null; try { pj = JSON.parse(store.get("pin") || "null"); } catch (e) {}
    S.el.querySelector("#smforget").hidden = !pj;
    const sq = new URLSearchParams(location.hash.slice(1));
    if (sq.has("ballot") && openShared(S, sq)) return;      /* a ballot someone shared: shown, never kept */
    if (SPOT && SPOT.st === S.code) { const s = SPOT; SPOT = null; placeHere(S, s.lon, s.lat, s.acc, s.lead, false).catch(() => {}); }
    else if (pj && pj.st === S.code && isFinite(pj.lat) && isFinite(pj.lon)) placeHere(S, pj.lon, pj.lat, 0, "", true).catch(() => {});
  }

  /* ---------- mounting ---------- */
  function mount(el) {
    el = el || document.querySelector("[data-sm]"); if (!el) return;
    const code = String(el.dataset.sm || "").toUpperCase();
    if (CUR && CUR.el === el && CUR.code === code) return;
    if (CUR && CUR.map) { CUR.map.destroy(); }
    if (!document.getElementById("sm-css")) { const s = document.createElement("style"); s.id = "sm-css"; s.textContent = ".sm{margin:22px 0 0;min-width:0;max-width:100%}\n.sm *{box-sizing:border-box}\n.sm h3.smh{font-family:var(--serif);font-weight:400;font-size:clamp(24px,3vw,32px);line-height:1.1;margin:0;display:flex;gap:8px 12px;align-items:center;flex-wrap:wrap}\n.sm h4{font:700 12px var(--sans);letter-spacing:.09em;text-transform:uppercase;color:var(--muted);margin:16px 0 0}\n.sm p{margin:8px 0 0;max-width:80ch;line-height:1.5;font-size:15px}\n.sm .smsub{color:var(--muted);font-size:14px}\n.sm a{color:var(--accent-ink,var(--accent))}\n.smchips{display:flex;flex-wrap:wrap;gap:6px;margin:12px 0 0}\n.smchips button,.smbtn{all:unset;box-sizing:border-box;cursor:pointer;min-height:40px;padding:0 14px;border-radius:999px;border:1px solid var(--line-strong);font:600 14px var(--sans);color:var(--ink);background:var(--surface);display:inline-flex;align-items:center;gap:6px}\n.smchips button[aria-pressed=\"true\"]{background:var(--ink);color:var(--bg);border-color:var(--ink)}\n.smchips button:focus-visible,.smbtn:focus-visible,.sm a:focus-visible,.smoff select:focus-visible{outline:3px solid var(--accent);outline-offset:2px}\n@media (pointer:coarse){.smchips button,.smbtn{min-height:44px}}\n.smoff{display:flex;flex-wrap:wrap;gap:6px 10px;align-items:center;margin:10px 0 0;font:700 12px var(--sans);letter-spacing:.08em;text-transform:uppercase;color:var(--muted)}\n.smoff select{min-height:44px;font:600 15px var(--sans);letter-spacing:0;text-transform:none;padding:6px 10px;border-radius:12px;border:1px solid var(--line-strong);background:var(--surface);color:var(--ink);max-width:100%}\n.smgrid{display:grid;grid-template-columns:minmax(0,1fr) minmax(220px,300px);gap:14px;margin:12px 0 0;align-items:start}\n@media (max-width:820px){.smgrid{grid-template-columns:minmax(0,1fr)}}\n.smmap{position:relative;height:clamp(300px,58vh,560px);border-radius:14px;overflow:hidden;background:var(--bg);border:1px solid var(--line);touch-action:pan-y;user-select:none;-webkit-user-select:none;cursor:pointer}\n.smmap.zoomed{touch-action:none;cursor:grab}.smmap.drag{cursor:grabbing}\n.smmap:focus{outline:none}.smmap:focus-visible{outline:2px solid var(--accent);outline-offset:2px}\n.smmap canvas{position:absolute;inset:0;width:100%;height:100%;display:block}\n.smmap .gtiles{display:none}\n.smmap .gpin{position:absolute;left:0;top:0;width:26px;height:34px;margin:-33px 0 0 -13px;pointer-events:none;filter:drop-shadow(0 3px 3px rgba(0,0,0,.35))}\n.smmap .gpin[hidden],.smmap .gbusy[hidden]{display:none}\n.smmap .gpin svg{display:block;width:26px;height:34px}.smmap .gpin path{fill:var(--ink);stroke:var(--bg);stroke-width:1.6}.smmap .gpin circle{fill:var(--bg)}\n.smmap .gbusy{position:absolute;left:8px;bottom:8px;font:600 11.5px var(--sans);color:var(--ink);background:var(--surface);border:1px solid var(--line);padding:3px 9px;border-radius:999px}\n.smzoom{display:flex;gap:6px;margin:0 0 8px}\n.smzoom button{all:unset;box-sizing:border-box;cursor:pointer;width:40px;height:40px;border-radius:12px;border:1px solid var(--line-strong);background:var(--surface);color:var(--ink);font:700 18px var(--sans);display:inline-flex;align-items:center;justify-content:center}\n.smzoom button:focus-visible{outline:3px solid var(--accent);outline-offset:2px}\n.smsvg{width:100%;height:auto;display:block;max-height:560px;border-radius:14px;border:1px solid var(--line);background:var(--bg)}\n.smsvg path{stroke:var(--surface);stroke-width:.6;vector-effect:non-scaling-stroke;cursor:pointer}\n.smsvg path.out{fill:none;stroke:var(--ink);stroke-width:1;pointer-events:none;opacity:.6}\n.smsvg path.hl{stroke:var(--ink);stroke-width:2}\n.smsvg path:focus{outline:none}.smsvg path:focus-visible{stroke:var(--ink);stroke-width:2.6}\n.smsvg .pin{fill:var(--ink);stroke:var(--bg);stroke-width:1.5;vector-effect:non-scaling-stroke}\n.smside{border:1px solid var(--line);border-radius:14px;padding:12px 14px;background:var(--surface);font-size:14.5px;line-height:1.5;min-height:90px}\n.smside h5{font:700 15.5px/1.35 var(--sans);margin:0}\n.smside .smr{border-top:1px solid var(--line);padding:8px 0 0;margin:8px 0 0}.smside .smr:first-of-type{border-top:0;margin-top:4px;padding-top:0}\n.smside p{font-size:14px;margin:4px 0 0}\n.smlegend{display:flex;flex-wrap:wrap;gap:6px 16px;margin:10px 0 0;font-size:13px;color:var(--muted);align-items:center}\n.smlegend span{display:inline-flex;align-items:center;gap:6px}\n.smlegend svg{width:18px;height:18px;flex:none}\n.smyours{margin:22px 0 0;border:1px solid var(--line);border-radius:16px;background:var(--surface);padding:14px 16px 16px}\n.smyours h4{margin-top:0}\n.smybar{display:flex;flex-wrap:wrap;gap:8px 12px;align-items:center;margin:10px 0 0}\n.smybtn{all:unset;box-sizing:border-box;cursor:pointer;min-height:44px;padding:0 16px;border-radius:999px;background:var(--ink);color:var(--bg);font:700 14px var(--sans);display:inline-flex;align-items:center;gap:8px}\n.smybtn svg{width:18px;height:18px;fill:none;stroke:currentColor;stroke-width:2}\n.smybtn:focus-visible{outline:3px solid var(--accent);outline-offset:2px}\n.smnote{font-size:14px;color:var(--ink)}\n#smres .smybar p{margin:0}\n.sm .tca-share.smsh,.smyours .tca-share.smsh{flex:none}\n.smlist{list-style:none;margin:12px 0 0;padding:0;display:grid;gap:8px}\n.smlist li{border:1px solid var(--line);border-left:5px solid var(--c,var(--line-strong));border-radius:12px;padding:9px 12px;background:var(--bg);min-width:0}\n.smlist li b{display:block;font-size:15px}\n.smlist li small{display:block;color:var(--muted);font-size:13px}\n.smlist li p{margin:4px 0 0;font-size:14px}\n.smlv{font:700 12px var(--sans);letter-spacing:.09em;text-transform:uppercase;color:var(--muted);margin:14px 0 0}\n.sm .tag.analysis{flex:none}\n.sm [hidden],.smyours [hidden]{display:none!important}"; document.head.appendChild(s); }
    const S = {el, code, chips: el.dataset.chips !== "0", lv: el.dataset.lv || "", night: !!el.dataset.night, go: null};
    CUR = S;
    S.go = st => { if (el.dataset.night) location.hash = "state=" + st; else { const q = new URLSearchParams(location.hash.slice(1)); q.set("st", st); history.replaceState(history.state, "", location.pathname + location.search + "#" + q.toString()); dispatchEvent(new HashChangeEvent("hashchange")); } };
    const start = () => needIdx().then(() => {
      if (CUR !== S) return;
      if (!IDX.st[code]) { el.innerHTML = ""; return; }
      return getJSON(url(`data/sm/${code.toLowerCase()}.json?v=${IDX.st[code]}`)).then(D => {
        if (CUR !== S || !el.isConnected) return;
        S.D = D; S.R = rows(D);
        S.kinds = new Set(["state"].concat(D.geo ? ["cd", "senate", "house", "county", "com", "park", "swcd", "mcd", "ward", "school", "hospital", "judicial"] : ["cd"]));
        if (!levels(S).includes(S.lv)) S.lv = defaultLevel(S);
        el.innerHTML = shell(S);
        fillOffices(S);
        el.querySelector("#smoff").addEventListener("change", e => { S.gk = e.target.value; drawMap(S); });
        el.addEventListener("click", e => { const b = e.target.closest("button[data-smlv]"); if (!b) return; level(b.dataset.smlv); });
        drawMap(S);
        wireYours(S);
      });
    }).catch(() => { if (CUR === S) el.innerHTML = `<p class="smsub">${esc(T("The state's map could not be loaded. Check your connection and open the page again."))}</p>`; });
    (LOC ? I18.ready : Promise.resolve()).then(start, start);
  }
  /* the page's own choice of races (Election Night's chips): the map follows it */
  function level(lv) {
    const S = CUR; if (!S || !S.el.isConnected) return; if (!S.D) { S.lv = lv; return; }
    const ls = levels(S); S.lv = ls.includes(lv) ? lv : defaultLevel(S);
    S.el.querySelectorAll("button[data-smlv]").forEach(b => b.setAttribute("aria-pressed", String(b.dataset.smlv === S.lv)));
    fillOffices(S); drawMap(S);
    const n = S.el.querySelector("#smnotes"); if (lv && !ls.includes(lv) && n) n.textContent = T("These races are not on the map: the model has no forecast for them that a map can show. The map shows {level} instead.", {level: T(LVW[S.lv] || "")});
  }
  window.SM = {mount, level};
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", () => mount()); else mount();
})();
