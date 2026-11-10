// Service worker mínimo para a PWA ser "instalável" e abrir rápido.
// Estratégia: network-first para dados; cache só do app shell (estáticos).
const CACHE = "financas-v1";
const SHELL = ["/static/styles.css", "/static/app.js", "/static/icon.svg", "/manifest.webmanifest"];

self.addEventListener("install", (e) => {
  e.waitUntil(caches.open(CACHE).then((c) => c.addAll(SHELL)).then(() => self.skipWaiting()));
});

self.addEventListener("activate", (e) => {
  e.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k)))
    ).then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (e) => {
  const url = new URL(e.request.url);
  // Nunca cachear dados financeiros nem chamadas autenticadas.
  if (url.pathname.startsWith("/api/")) return;
  if (e.request.method !== "GET") return;
  if (SHELL.includes(url.pathname)) {
    e.respondWith(caches.match(e.request).then((r) => r || fetch(e.request)));
  }
});
