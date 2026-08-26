const CACHE_NAME = "findmybin-v11";

const APP_SHELL = [
  "/",
  "/static/style.css",
  "/static/js/app.js",
  "/static/manifest.json",
];

self.addEventListener("install", function (event) {
  self.skipWaiting();

  event.waitUntil(
    caches.open(CACHE_NAME).then(function (cache) {
      return cache.addAll(APP_SHELL);
    }),
  );
});

self.addEventListener("activate", function (event) {
  self.clients.claim();

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
    fetch(event.request)
      .then(function (networkResponse) {
        const responseCopy = networkResponse.clone();

        caches.open(CACHE_NAME).then(function (cache) {
          cache.put(event.request, responseCopy);
        });

        return networkResponse;
      })
      .catch(function () {
        return caches.match(event.request);
      }),
  );
});
