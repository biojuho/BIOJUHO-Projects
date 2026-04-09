const CACHE_NAME = "agriguard-v2";
const STATIC_ASSETS = ["/", "/index.html"];
const CACHEABLE_API_PATHS = new Set();

function isSameOrigin(url) {
  return url.origin === self.location.origin;
}

function isCacheableStaticResponse(response) {
  return response.ok;
}

function isCacheableApiResponse(request, response, url) {
  const cacheControl = response.headers.get("Cache-Control") || "";
  return (
    CACHEABLE_API_PATHS.has(url.pathname) &&
    response.ok &&
    !cacheControl.includes("no-store") &&
    !request.headers.has("Authorization")
  );
}

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches
      .open(CACHE_NAME)
      .then((cache) => cache.addAll(STATIC_ASSETS))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) =>
        Promise.all(keys.filter((key) => key !== CACHE_NAME).map((key) => caches.delete(key)))
      )
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (event) => {
  const { request } = event;
  const url = new URL(request.url);

  if (request.method !== "GET" || !isSameOrigin(url)) {
    return;
  }

  if (url.pathname.startsWith("/api/")) {
    event.respondWith(
      fetch(request).then((response) => {
        if (isCacheableApiResponse(request, response, url)) {
          const clone = response.clone();
          void caches.open(CACHE_NAME).then((cache) => cache.put(request, clone));
        }
        return response;
      })
    );
    return;
  }

  event.respondWith(
    caches.match(request).then((cached) => {
      if (cached) {
        return cached;
      }

      return fetch(request).then((response) => {
        if (isCacheableStaticResponse(response)) {
          const clone = response.clone();
          void caches.open(CACHE_NAME).then((cache) => cache.put(request, clone));
        }
        return response;
      });
    })
  );
});
