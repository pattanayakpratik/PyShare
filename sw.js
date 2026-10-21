/* ==========================================================================
   PyShare v4.6.0 - Progressive Web App Service Worker
   ========================================================================== */

const CACHE_NAME = 'pyshare-shell-v4.6.0';
const PRECACHE_RESOURCES = [
  '/',
  '/guide.html',
  '/manifest.json',
  '/styles.css',
  '/client_styles.css',
  '/scripts.js',
  '/feedback.js',
  '/app_icon.png',
  '/app_icon.ico'
];

self.addEventListener('install', (event) => {
  self.skipWaiting();
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      return cache.addAll(PRECACHE_RESOURCES).catch(() => {});
    })
  );
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) => {
      return Promise.all(
        keys.filter((key) => key !== CACHE_NAME).map((key) => caches.delete(key))
      );
    }).then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', (event) => {
  const url = new URL(event.request.url);

  // Dynamic endpoints must bypass cache completely
  if (
    url.pathname.startsWith('/api/') ||
    url.pathname.startsWith('/view/') ||
    url.pathname.startsWith('/download/') ||
    url.pathname.startsWith('/login') ||
    url.pathname === '/qrcode.png' ||
    event.request.method !== 'GET'
  ) {
    return;
  }

  // Network first with cache fallback
  event.respondWith(
    fetch(event.request)
      .then((response) => {
        if (response.status === 200) {
          const clone = response.clone();
          caches.open(CACHE_NAME).then((cache) => cache.put(event.request, clone));
        }
        return response;
      })
      .catch(() => caches.match(event.request))
  );
});
