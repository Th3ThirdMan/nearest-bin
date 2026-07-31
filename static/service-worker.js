const CACHE_NAME = "findmybin-v2";

const APP_SHELL = [
  "/",
  "/static/style.css",
  "/static/js/app.js",
  "/static/manifest.json",
];

self.addEventListener("install", function (event) {
  event.waitUntil(
    caches.open(CACHE_NAME).then(function (cache) {
      return cache.addAll(APP_SHELL);
    }),
  );
});

self.addEventListener("activate", function (event) {
  event.waitUntil(
    caches.keys().then(function (cacheNames) {
      return Promise.all(
        cacheNames
          .filter(function (cacheName) {
            return cacheName !== CACHE_NAME;
          })
          .map(function (cacheName) {
            return caches.delete(cacheName);
          }),
      );
    }),
  );
});

self.addEventListener("fetch", function (event) {
  if (event.request.method !== "GET") {
    return;
  }

  event.respondWith(
    caches.match(event.request).then(function (cachedResponse) {
      return cachedResponse || fetch(event.request);
    }),
  );
});
