const SCOPE = new URL(self.registration.scope).pathname, PRE = "civic-" + SCOPE + ":", V = PRE + "4.1.050", OLD = true;
const SHELL = ["./", "./index.html"];
self.addEventListener("install", e => { e.waitUntil(caches.open(V).then(c => c.addAll(SHELL)).then(() => self.skipWaiting())); });
self.addEventListener("activate", e => { e.waitUntil(caches.keys().then(ks => Promise.all(ks.filter(k => (k.startsWith(PRE) && k !== V) || (OLD && /^civic-\d/.test(k))).map(k => caches.delete(k)))).then(() => self.clients.claim())); });
self.addEventListener("fetch", e => {
  const r = e.request; if (r.method !== "GET" || r.headers.has("range")) return;
  const u = new URL(r.url); if (u.origin !== location.origin) return;
  /* The cache only ever helps: when it cannot be opened or read (storage full, blocked or cleared), the network answers. */
  const store = (key, res) => { try { const copy = res.clone(); caches.open(V).then(c => c.put(key, copy)).catch(() => {}); } catch (_) {} };
  if (/\/(data|photos|og)\//.test(u.pathname)) {
    e.respondWith(caches.open(V).then(c => c.match(r)).catch(() => undefined)
      .then(hit => hit || fetch(r).then(res => { if (res.ok) store(r, res); return res; })));
    return;
  }
  if (r.mode === "navigate" || /\/index\.html$/.test(u.pathname)) {
    e.respondWith(fetch(r).then(res => { if (res.ok) store("./index.html", res); return res; })
      .catch(() => caches.open(V).then(c => c.match("./index.html")).catch(() => undefined)
        .then(hit => hit || caches.match(new URL("../app/offline.html", self.registration.scope).href).catch(() => undefined))
        .then(hit => hit || Response.error())));
    return;
  }
  if (/\.(js|css|ttf|woff2?|svg|png|webp|json)$/.test(u.pathname) && !u.pathname.startsWith("/night-live/"))
    e.respondWith(fetch(r).catch(() => caches.match(r).catch(() => undefined).then(hit => hit || Response.error())));
});
