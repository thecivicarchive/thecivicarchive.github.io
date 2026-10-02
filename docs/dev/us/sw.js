const V = "civic-4.0.086";
const SHELL = ["./", "./index.html", "./manifest.webmanifest"];
self.addEventListener("install", e => { e.waitUntil(caches.open(V).then(c => c.addAll(SHELL)).then(() => self.skipWaiting())); });
self.addEventListener("activate", e => { e.waitUntil(caches.keys().then(ks => Promise.all(ks.filter(k => k !== V).map(k => caches.delete(k)))).then(() => self.clients.claim())); });
self.addEventListener("fetch", e => {
  const r = e.request; if (r.method !== "GET") return;
  const u = new URL(r.url); if (u.origin !== location.origin) return;
  if (/\/(data|photos|og)\//.test(u.pathname)) {
    e.respondWith(caches.open(V).then(c => c.match(r).then(hit => hit || fetch(r).then(res => { if (res.ok) c.put(r, res.clone()); return res; }))));
    return;
  }
  if (r.mode === "navigate" || /\/index\.html$/.test(u.pathname)) {
    e.respondWith(fetch(r).then(res => { if (res.ok) caches.open(V).then(c => c.put("./index.html", res.clone())); return res; })
      .catch(() => caches.match("./index.html")));
  }
});
