// Minimal app-shell cache so the kiosk still loads if the network drops.
const CACHE = "kiosk-shell-v1";
const SHELL = ["./index.html", "./styles.css", "./app.js", "./manifest.webmanifest", "./icon.svg"];

self.addEventListener("install", (e) => {
  e.waitUntil(caches.open(CACHE).then((c) => c.addAll(SHELL)).then(() => self.skipWaiting()));
});
self.addEventListener("activate", (e) => {
  e.waitUntil(caches.keys().then((ks) => Promise.all(ks.filter((k) => k !== CACHE).map((k) => caches.delete(k)))));
});
self.addEventListener("fetch", (e) => {
  const url = new URL(e.request.url);
  // Never cache API calls; only serve the static shell from cache.
  if (url.pathname.startsWith("/api/")) return;
  e.respondWith(caches.match(e.request).then((r) => r || fetch(e.request)));
});
