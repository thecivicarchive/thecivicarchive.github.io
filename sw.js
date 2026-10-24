/* The Civic Archive as an app (John, 2026-10-17): the worker for the whole copy, at the copy's root.
   - Pages come from the network first, every time there is a connection, so a reader online always gets the newest page.
     A copy of each page, and of the small files it used, is kept on this device as the reader opens them, so the pages
     already opened still work with no connection. Anything new needs one.
   - What is kept stays within a budget (about 60 MB); the copies used longest ago go first. The Congress pages' own worker
     keeps its copies apart from this budget; "Clear what is kept" clears those too.
   - Never kept: big media (the scenes on the way in and the places to sit, video and sound, models, anything over a few
     MB), and Election Night's live figures (/night-live/), which always come from the network.
   - The live site's worker leaves everything under /dev/ and /night-live/ alone; the draft's leaves alone everything
     outside /dev/ except the shared street maps (/maps/). Other servers' addresses are never touched.
   - Its caches are named for its copy (tca-app-live-..., tca-app-dev-...), and it deletes only its own.
   Nothing here is sent anywhere: the worker only keeps copies of this site's own pages on this device. */
const COPY = "live", CORE = "97bef292ee";
const PRE = "tca-app-" + COPY + "-", KEPT = PRE + "kept", CORE_CACHE = PRE + "core-" + CORE, DB = "tca-app-" + COPY;
const SCOPE = new URL(self.registration.scope), OFFLINE = new URL("app/offline.html", SCOPE).href;
const TEST = /^(127\.0\.0\.1|localhost|\[::1\])$/.test(self.location.hostname);      // the test hooks answer only on this computer
let BUDGET = 60e6, cut = false;
const MB = 1e6, LIMIT = {page: 8 * MB, text: 5 * MB, other: 2 * MB};
/* what is never kept: the scenes and their files, the places to sit, models, video and sound */
const NOKEEP = /^(nightsky|pollingplace|recordroom|cabin_assets)\/|^night\/sky\/|^ballot\/polling-place\/|^reading-room\/|^cabin(\.html|3d\.js)?$|^shell\/companions\/models\/|^app\/offline\.html$|^_|\.(glb|gltf|bin|mp4|m4v|webm|mov|mp3|m4a|ogg|oga|wav|flac|hdr|exr|ktx2|basis|zip|pdf)$/i;
const FIXED = /\.[0-9a-f]{10}\.(js|css|png|jpe?g|webp|avif|svg|json|ttf|woff2?)$/i;      // named by a hash of their contents: never change

/* Where a request goes. A pure function, so the test hook can ask it about any address and either copy. */
function route(href, o) {
  const u = new URL(href);
  if ((o.method || "GET") !== "GET" || o.range) return "pass";
  if (u.origin !== o.origin) return "pass";
  const p = u.pathname, scope = o.scope;
  if (o.copy === "live") { if (p.startsWith("/dev/") || p === "/dev" || p.startsWith("/night-live/")) return "pass"; }
  else if (!p.startsWith(scope) && !p.startsWith("/maps/")) return "pass";
  if (p.startsWith("/night-live/")) return "pass";
  const maps = p.startsWith("/maps/") && !p.startsWith(scope + "maps/");
  const rel = maps ? p.slice(1) : p.slice(scope.length);
  if (!maps && (rel === "sw.js" || rel.startsWith("ballot/kept/"))) return "pass";      // the worker itself; the kept ballot has its own
  const nav = o.mode === "navigate";
  if (!maps && NOKEEP.test(rel)) return nav ? "nokeep" : "pass";
  if (nav) return "page";
  if (maps || FIXED.test(p)) return "fixed";
  return "file";
}

/* ---------- the record of what is kept: one row per copy (address, size, last used, page title) ---------- */
function db() {
  return new Promise((ok, no) => {
    const q = indexedDB.open(DB, 1);
    q.onupgradeneeded = () => q.result.createObjectStore("kept", {keyPath: "u"});
    q.onsuccess = () => ok(q.result); q.onerror = () => no(q.error);
  });
}
function tx(mode, act) {
  return db().then(d => new Promise((ok, no) => {
    const t = d.transaction("kept", mode), s = t.objectStore("kept"), r = act(s);
    t.oncomplete = () => { d.close(); ok(r && "result" in r ? r.result : undefined); };
    t.onerror = () => { d.close(); no(t.error); };
  }));
}
const note = row => tx("readwrite", s => s.put(row)).catch(() => {});
const touch = u => tx("readwrite", s => { const g = s.get(u); g.onsuccess = () => { if (g.result) { g.result.t = Date.now(); s.put(g.result); } }; }).catch(() => {});
const rows = () => tx("readonly", s => s.getAll()).then(r => r || []).catch(() => []);

let trimT = 0;
function trimSoon() { clearTimeout(trimT); trimT = setTimeout(trim, 2000); }
async function trim() {
  const all = await rows();
  let total = all.reduce((a, r) => a + (r.s || 0), 0);
  if (total <= BUDGET) return {total, dropped: 0};
  all.sort((a, b) => a.t - b.t);      // the copies used longest ago go first
  const c = await caches.open(KEPT);
  let dropped = 0;
  for (const r of all) {
    if (total <= BUDGET * 0.85) break;
    await c.delete(r.u).catch(() => {});
    await tx("readwrite", s => s.delete(r.u)).catch(() => {});
    total -= r.s || 0; dropped++;
  }
  return {total, dropped};
}

/* ---------- keeping a copy ---------- */
function kind(res, isPage) {
  const t = (res.headers.get("content-type") || "").toLowerCase();
  if (isPage) return t.includes("text/html") ? "page" : null;
  if (/^(video|audio|model)\//.test(t) || t.includes("octet-stream")) return null;
  return /json|javascript|text\/|css|svg|xml/.test(t) ? "text" : "other";
}
async function keep(req, res, isPage) {
  try {
    if (!res || res.status !== 200 || res.type !== "basic" || /no-store/i.test(res.headers.get("cache-control") || "")) return;
    const k = kind(res, isPage); if (!k) return;
    const lim = LIMIT[k], len = +res.headers.get("content-length") || 0;
    if (len > lim) return;
    const body = await res.clone().blob();
    if (body.size > lim) return;
    const u = req.url.split("#")[0];
    const row = {u, s: body.size, t: Date.now(), p: isPage ? 1 : 0};
    if (isPage) {
      const m = /<title[^>]*>([\s\S]*?)<\/title>/i.exec(await body.slice(0, 65536).text());
      row.n = m ? m[1].replace(/\s+/g, " ").trim().replace(/&amp;/g, "&").replace(/&rsquo;/g, "’").replace(/&middot;/g, "·").replace(/&#39;|&apos;/g, "'").replace(/&quot;/g, '"').replace(/&lt;/g, "<").replace(/&gt;/g, ">").slice(0, 140) : "";
    }
    /* the body is already decoded: the headers that describe the network's encoding and length no longer fit it */
    const h = new Headers(res.headers);
    for (const x of ["content-encoding", "content-length", "transfer-encoding"]) h.delete(x);
    const c = await caches.open(KEPT);
    await c.put(u, new Response(body, {status: 200, statusText: res.statusText, headers: h}));
    await note(row);
    trimSoon();
  } catch (e) {}
}
const net = req => cut ? Promise.reject(new TypeError("no connection (test)")) : fetch(req);
async function kept(req, loose) {
  try {      // a cache that will not open or read counts as "nothing kept", never as an error
    const c = await caches.open(KEPT);
    const u = req.url.split("#")[0];
    const hit = await c.match(u) || (loose ? await c.match(u, {ignoreSearch: true}) : null);
    if (hit) touch(hit.url || u);
    return hit || null;
  } catch (e) { return null; }
}
const PLAIN = () => new Response("You're offline. Pages you've opened are still here once you're back online.", {status: 503, headers: {"Content-Type": "text/plain; charset=utf-8"}});
async function offline() {
  try {
    const hit = await caches.match(OFFLINE, {cacheName: CORE_CACHE});
    if (!hit) return PLAIN();
    const text = (await hit.text()).split("__TCA_SCOPE__").join(SCOPE.href);
    return new Response(text, {status: 503, headers: {"Content-Type": "text/html; charset=utf-8", "Cache-Control": "no-store"}});
  } catch (e) { return PLAIN(); }
}

/* ---------- the four ways a request is answered ---------- */
async function page(e) {
  try {
    const res = await net(e.request);
    if (res.ok) e.waitUntil(keep(e.request, res.clone(), true));
    return res;
  } catch (err) {
    return (await kept(e.request, true)) || offline();
  }
}
async function nokeep(e) {
  try { return await net(e.request); } catch (err) { return offline(); }
}
async function file(e) {
  try {
    const res = await net(e.request);
    if (res.ok) e.waitUntil(keep(e.request, res.clone(), false));
    return res;
  } catch (err) {
    return (await kept(e.request, false)) || Response.error();
  }
}
async function fixed(e) {
  const hit = await kept(e.request, false);      // a failing cache falls through to the network
  if (hit) return hit;
  try {
    const res = await net(e.request);
    if (res.ok) e.waitUntil(keep(e.request, res.clone(), false));
    return res;
  } catch (err) { return Response.error(); }
}
const WAYS = {page, nokeep, file, fixed};

self.addEventListener("install", e => {
  e.waitUntil(caches.open(CORE_CACHE).then(c => c.add(new Request(OFFLINE, {cache: "reload"}))).catch(() => {}).then(() => self.skipWaiting()));
});
self.addEventListener("activate", e => {
  e.waitUntil(caches.keys().then(ks => Promise.all(ks.filter(k => k.startsWith(PRE) && k !== KEPT && k !== CORE_CACHE).map(k => caches.delete(k))))
    .then(() => self.clients.claim()));
});
self.addEventListener("fetch", e => {
  const r = e.request;
  let way;
  try {
    way = route(r.url, {method: r.method, range: r.headers.has("range"), origin: SCOPE.origin, scope: SCOPE.pathname, copy: COPY, mode: r.mode});
  } catch (err) { return; }
  if (way === "pass" || !WAYS[way]) return;
  e.respondWith(WAYS[way](e).catch(() => way === "page" || way === "nokeep" ? offline() : Response.error()));
});

/* The Congress pages (<root>us/) have a worker of their own, which keeps the bills, votes, portraits and previews a reader
   opens in caches named "civic-<its folder>:<version>" (and, on the live copy, the older "civic-<version>"). They sit
   outside this worker's budget; the app page counts them apart, and "Clear what is kept" clears them too. */
const US = "civic-" + new URL("us/", SCOPE).pathname + ":";
const usCaches = () => caches.keys().then(ks => ks.filter(k => k.startsWith(US) || (COPY === "live" && /^civic-\d/.test(k))));
const usCount = () => usCaches().then(ks => Promise.all(ks.map(k => caches.open(k).then(c => c.keys()).then(r => r.length)))).then(n => n.reduce((a, b) => a + b, 0)).catch(() => 0);

/* ---------- the page's questions: how much is kept (the app page shows it), forget it all; and the test hooks ---------- */
self.addEventListener("message", e => {
  const m = e.data || {}, reply = x => { try { (e.ports && e.ports[0] ? e.ports[0] : e.source).postMessage(Object.assign({tca: "app", re: m.tca}, x)); } catch (err) {} };
  if (m.tca === "stats") e.waitUntil(Promise.all([rows(), usCount()]).then(([all, us]) => reply({pages: all.filter(r => r.p).length, files: all.filter(r => !r.p).length,
    bytes: all.reduce((a, r) => a + (r.s || 0), 0), budget: BUDGET, copy: COPY, us})));
  else if (m.tca === "forget") e.waitUntil(caches.delete(KEPT).then(() => tx("readwrite", s => s.clear()))
    .then(() => usCaches()).then(ks => Promise.all(ks.map(k => caches.delete(k))))
    .then(() => reply({ok: true}), () => reply({ok: false})));
  else if (!TEST) return;
  else if (m.tca === "cut") { cut = !!m.on; reply({cut}); }
  else if (m.tca === "route") reply({way: route(m.url, {method: m.method || "GET", range: !!m.range, origin: m.origin || SCOPE.origin, scope: m.scope || SCOPE.pathname, copy: m.copy || COPY, mode: m.mode || "no-cors"})});
  else if (m.tca === "budget") { BUDGET = +m.bytes || BUDGET; e.waitUntil(trim().then(r => reply(r))); }
});
