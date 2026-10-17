/* The kept ballot's worker (John, 2026-10-15). It looks after this folder alone: the kept page, its manifest and its icons, so that
   the page opens with no signal. The ballot itself is in the device's own storage, never here, and nothing is ever sent anywhere.
   Every other address on the site passes it by, so no other page is ever served from here. The page is fetched fresh whenever there
   is a signal (it waits three seconds for one, then opens the kept copy); a copy is kept in the cache and, because another of the
   site's workers may clear the cache, in IndexedDB too. The draft (/dev/ballot/kept/) and the live site (/ballot/kept/) share one
   address, so every name here carries this worker's own folder: neither copy ever serves, keeps or deletes the other's. */
const SCOPE = new URL(self.registration.scope).pathname, PRE = "kept:" + SCOPE + ":", V = PRE + "248aed6c0b", KEY = "index:" + SCOPE, FILES = ["./", "./manifest.webmanifest", "./apple-touch-icon.png", "./icon-192.png", "./icon-512.png", "./icon-512-maskable.png"];
const idb = (mode, act) => new Promise((ok, no) => { const q = indexedDB.open("tca-kept-page", 1);
  q.onupgradeneeded = () => q.result.createObjectStore("page"); q.onerror = () => no(q.error);
  q.onsuccess = () => { const t = q.result.transaction("page", mode), r = act(t.objectStore("page")); t.oncomplete = () => ok(r && r.result); t.onerror = () => no(t.error); }; });
const keepCopy = text => idb("readwrite", s => s.put(text, KEY)).catch(() => {});
const theCopy = () => idb("readonly", s => s.get(KEY)).catch(() => null);
const kept = () => caches.open(V).then(c => c.match("./")).catch(() => null).then(hit => hit || theCopy().then(t => t ? new Response(t, {headers: {"Content-Type": "text/html; charset=utf-8"}}) : null));
self.addEventListener("install", e => e.waitUntil(caches.open(V).then(c => c.addAll(FILES))
  .then(() => fetch("./", {cache: "no-store"}).then(r => r.ok ? r.text().then(keepCopy) : null).catch(() => null)).then(() => self.skipWaiting())));
self.addEventListener("activate", e => e.waitUntil(caches.keys().then(ks => Promise.all(ks.filter(k => k.startsWith(PRE) && k !== V).map(k => caches.delete(k))))
  .then(() => self.clients.claim())));
self.addEventListener("fetch", e => {
  const r = e.request; if (r.method !== "GET") return;
  const u = new URL(r.url), base = new URL(self.registration.scope);
  if (u.origin !== base.origin || !u.pathname.startsWith(base.pathname)) return;      // nothing outside this folder, ever
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
