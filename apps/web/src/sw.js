/**
 * AquaSense AI — Service Worker
 * Caches the app shell (HTML, CSS, JS) for offline viewing of the UI.
 * API calls always go to the network; only static assets are cached.
 */

const CACHE = "aquasense-v14";
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

  // Always fetch API and auth calls from network — never cache user-specific data
  if (url.pathname.startsWith("/api/") || url.pathname.startsWith("/auth/")) {
    // Pass through with original request (preserves cookies) and bypass HTTP cache
    e.respondWith(
      fetch(e.request, { cache: "no-store" }).catch(() =>
        new Response(JSON.stringify({ detail: "Offline" }), {
          status: 503,
          headers: { "Content-Type": "application/json" },
        })
      )
    );
    return;
  }

  // Cache-first for static shell assets only
  e.respondWith(
    caches.match(e.request).then(cached => cached || fetch(e.request).then(resp => {
      if (resp.ok && e.request.method === "GET") {
        caches.open(CACHE).then(c => c.put(e.request, resp.clone()));
      }
      return resp;
    }))
  );
});
