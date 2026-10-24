/* The kept ballot's worker (John, 2026-10-15). It looks after this folder alone: the kept page, its manifest and its icons, so that
   the page opens with no signal. The ballot itself is in the device's own storage, never here, and nothing is ever sent anywhere.
   Every other address on the site passes it by, so no other page is ever served from here. The page is fetched fresh whenever there
   is a signal (it waits three seconds for one, then opens the kept copy); a copy is kept in the cache and, because another of the
   site's workers may clear the cache, in IndexedDB too. The draft (/dev/ballot/kept/) and the live site (/ballot/kept/) share one
   address, so every name here carries this worker's own folder: neither copy ever serves, keeps or deletes the other's.
   The reader's language (2026-10-23): the page's words in another language are the site's language files (shell/lang/<code>.<bundle>.
   <hash>.json, outside this folder), which the page's head script asks for by name. This worker keeps the ones the page names
   (it says which after registering, so the first open with no signal after keeping a ballot works) and any it sees fetched, in a
   cache and in IndexedDB of their own, and answers those names from them with no signal; a file is never changed under its name, so
   a kept copy is served first. It keeps one language's files at a time. Nothing else outside this folder is ever touched. */
const SCOPE = new URL(self.registration.scope).pathname, PRE = "kept:" + SCOPE + ":", V = PRE + "94c12e4d0d", KEY = "index:" + SCOPE, FILES = ["./", "./manifest.webmanifest", "./apple-touch-icon.png", "./icon-192.png", "./icon-512.png", "./icon-512-maskable.png"];
const ROOT = SCOPE.replace(/ballot\/kept\/$/, ""), LANGS = ROOT + "shell/lang/", LC = "keptlang:" + SCOPE, LK = "lang:" + LANGS;      // the copy's root: /dev/ or /
const isLang = p => typeof p === "string" && p.startsWith(LANGS) && /^[A-Za-z]{2,3}(?:-[A-Za-z]{2,4})?\.[a-z]+\.[0-9a-f]{10}\.json$/.test(p.slice(LANGS.length));
const idb = (mode, act) => new Promise((ok, no) => { const q = indexedDB.open("tca-kept-page", 1);
  q.onupgradeneeded = () => q.result.createObjectStore("page"); q.onerror = () => no(q.error);
  q.onsuccess = () => { const t = q.result.transaction("page", mode), r = act(t.objectStore("page")); t.oncomplete = () => ok(r && r.result); t.onerror = () => no(t.error); }; });
const keepCopy = text => idb("readwrite", s => s.put(text, KEY)).catch(() => {});
const theCopy = () => idb("readonly", s => s.get(KEY)).catch(() => null);
const kept = () => caches.open(V).then(c => c.match("./")).catch(() => null).then(hit => hit || theCopy().then(t => t ? new Response(t, {headers: {"Content-Type": "text/html; charset=utf-8"}}) : null));
/* a language file: kept in the cache and in IndexedDB under its own name; the kept copy first, else the network (and kept then) */
const JSONH = {headers: {"Content-Type": "application/json; charset=utf-8"}};
const keepLang = (p, res) => res.text().then(t => Promise.all([caches.open(LC).then(c => c.put(p, new Response(t, JSONH))).catch(() => {}),
  idb("readwrite", s => s.put(t, "lang:" + p)).catch(() => {})])).catch(() => {});
const langHit = p => caches.open(LC).then(c => c.match(p)).catch(() => null)
  .then(hit => hit || idb("readonly", s => s.get("lang:" + p)).catch(() => null).then(t => t ? new Response(t, JSONH) : null));
const langFile = p => langHit(p).then(hit => hit || fetch(p, {credentials: "same-origin"}).then(res => { if (res.ok) keepLang(p, res.clone()); return res; }));
/* only the files named last are kept: the others (another language, an older copy) go */
const pruneLang = keep => caches.open(LC).then(c => c.keys().then(ks => Promise.all(ks.filter(r => !keep.includes(new URL(r.url).pathname)).map(r => c.delete(r))))).catch(() => {})
  .then(() => idb("readwrite", s => { const q = s.getAllKeys(); q.onsuccess = () => q.result.forEach(k => { if (String(k).startsWith(LK) && !keep.includes(String(k).slice(5))) s.delete(k); }); return q; }).catch(() => {}));
self.addEventListener("message", e => {
  const d = e.data || {}; if (!Array.isArray(d.keepLang)) return;
  const want = [...new Set(d.keepLang.map(String))].filter(isLang).slice(0, 12); if (!want.length) return;
  e.waitUntil(Promise.all(want.map(p => langHit(p).then(hit => hit || fetch(p, {credentials: "same-origin"}).then(r => r.ok ? keepLang(p, r) : null)).catch(() => null)))
    .then(() => pruneLang(want)));
});
self.addEventListener("install", e => e.waitUntil(caches.open(V).then(c => c.addAll(FILES))
  .then(() => fetch("./", {cache: "no-store"}).then(r => r.ok ? r.text().then(keepCopy) : null).catch(() => null)).then(() => self.skipWaiting())));
self.addEventListener("activate", e => e.waitUntil(caches.keys().then(ks => Promise.all(ks.filter(k => k.startsWith(PRE) && k !== V).map(k => caches.delete(k))))
  .then(() => self.clients.claim())));
self.addEventListener("fetch", e => {
  const r = e.request; if (r.method !== "GET") return;
  const u = new URL(r.url), base = new URL(self.registration.scope);
  if (u.origin === base.origin && !u.search && isLang(u.pathname)) { e.respondWith(langFile(u.pathname).catch(() => Response.error())); return; }      // the reader's language files
  if (u.origin !== base.origin || !u.pathname.startsWith(base.pathname)) return;      // nothing else outside this folder, ever
  const rel = "./" + u.pathname.slice(base.pathname.length);
  if (r.mode === "navigate" || rel === "./" || rel === "./index.html") {
    const net = fetch(r).then(res => { if (res.ok) { const a = res.clone(); caches.open(V).then(c => c.put("./", a)).catch(() => {}); res.clone().text().then(keepCopy).catch(() => {}); } return res; });
    const slow = new Promise(ok => setTimeout(() => ok(null), 3000));      // one bar of signal at a polling place: wait three seconds, no more
    e.respondWith(Promise.race([net, slow]).then(first => first || kept().then(k => { if (k) { e.waitUntil(net.catch(() => {})); return k; } return net; }))
      .catch(() => kept().then(k => k || Response.error())));
    return;
  }
  if (FILES.includes(rel)) e.respondWith(caches.open(V).then(c => c.match(rel)).catch(() => null).then(hit => hit || fetch(r)));
});
