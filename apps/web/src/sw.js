/**
 * AquaSense AI — Service Worker
 * Caches the app shell (HTML, CSS, JS) for offline viewing of the UI.
 * API calls always go to the network; only static assets are cached.
 */

const CACHE = "aquasense-v8";
const SHELL = ["/", "/app.js", "/manifest.json"];

self.addEventListener("install", e => {
  e.waitUntil(
    caches.open(CACHE).then(c => c.addAll(SHELL)).then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", e => {
  e.waitUntil(
    caches.keys().then(keys =>
      Promise.all(keys.filter(k => k !== CACHE).map(k => caches.delete(k)))
    ).then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", e => {
  const url = new URL(e.request.url);

  // Always fetch API calls from network — never serve stale analysis data
  if (url.pathname.startsWith("/api/")) {
    e.respondWith(fetch(e.request));
    return;
  }

  // Cache-first for static shell assets
  e.respondWith(
    caches.match(e.request).then(cached => cached || fetch(e.request).then(resp => {
      if (resp.ok && e.request.method === "GET") {
        caches.open(CACHE).then(c => c.put(e.request, resp.clone()));
      }
      return resp;
    }))
  );
});
