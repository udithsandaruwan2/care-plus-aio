/// <reference lib="webworker" />
/**
 * Care Plus service worker (Step 93).
 * Workbox precache + runtime caches, with Step 41 Web Push handlers preserved.
 */
import { clientsClaim } from 'workbox-core';
import { cleanupOutdatedCaches, createHandlerBoundToURL, precacheAndRoute } from 'workbox-precaching';
import { NavigationRoute, registerRoute } from 'workbox-routing';
import { CacheFirst, NetworkFirst, StaleWhileRevalidate } from 'workbox-strategies';
import { CacheableResponsePlugin } from 'workbox-cacheable-response';
import { ExpirationPlugin } from 'workbox-expiration';

declare let self: ServiceWorkerGlobalScope;

self.skipWaiting();
clientsClaim();

precacheAndRoute(self.__WB_MANIFEST);
cleanupOutdatedCaches();

// App-shell navigations: serve index.html when offline (SPA).
registerRoute(
  new NavigationRoute(createHandlerBoundToURL('/index.html'), {
    denylist: [/^\/api\//, /^\/ws\//, /^\/offline\.html$/],
  }),
);

// Self-hosted font files (fontsource) — long-lived cache.
registerRoute(
  ({ request, url }) =>
    request.destination === 'font' ||
    /\.(?:woff2?|ttf|otf)$/i.test(url.pathname) ||
    (url.pathname.includes('/assets/') && /\.woff2?$/i.test(url.pathname)),
  new CacheFirst({
    cacheName: 'careplus-fonts',
    plugins: [
      new CacheableResponsePlugin({ statuses: [0, 200] }),
      new ExpirationPlugin({ maxEntries: 40, maxAgeSeconds: 60 * 60 * 24 * 365 }),
    ],
  }),
);

// Built CSS / JS / images — stale-while-revalidate.
registerRoute(
  ({ request, url }) =>
    url.origin === self.location.origin &&
    (request.destination === 'script' ||
      request.destination === 'style' ||
      request.destination === 'image' ||
      /\.(?:js|css|png|svg|ico|webp)$/i.test(url.pathname)),
  new StaleWhileRevalidate({
    cacheName: 'careplus-static',
    plugins: [
      new CacheableResponsePlugin({ statuses: [0, 200] }),
      new ExpirationPlugin({ maxEntries: 80, maxAgeSeconds: 60 * 60 * 24 * 30 }),
    ],
  }),
);

// Same-origin API — network first, short offline fallback.
registerRoute(
  ({ url }) => url.origin === self.location.origin && url.pathname.startsWith('/api/'),
  new NetworkFirst({
    cacheName: 'careplus-api',
    networkTimeoutSeconds: 8,
    plugins: [
      new CacheableResponsePlugin({ statuses: [0, 200] }),
      new ExpirationPlugin({ maxEntries: 40, maxAgeSeconds: 60 * 5 }),
    ],
  }),
);

/* ── Web Push (Step 41) — preserved from public/sw.js ─────────────── */

self.addEventListener('push', (event) => {
  let data: { title?: string; body?: string; url?: string } = {
    title: 'Care Plus',
    body: '',
    url: '/',
  };
  try {
    if (event.data) {
      data = { ...data, ...event.data.json() };
    }
  } catch {
    /* ignore malformed payload */
  }
  event.waitUntil(
    self.registration.showNotification(data.title || 'Care Plus', {
      body: data.body || '',
      icon: '/icons/icon-192.png',
      badge: '/icons/icon-192.png',
      data: { url: data.url || '/' },
    }),
  );
});

self.addEventListener('notificationclick', (event) => {
  event.notification.close();
  const target = (event.notification.data && event.notification.data.url) || '/';
  event.waitUntil(
    self.clients.matchAll({ type: 'window', includeUncontrolled: true }).then((list) => {
      for (const client of list) {
        if ('url' in client && String(client.url).includes(target) && 'focus' in client) {
          return (client as WindowClient).focus();
        }
      }
      if (self.clients.openWindow) {
        return self.clients.openWindow(target);
      }
      return undefined;
    }),
  );
});
