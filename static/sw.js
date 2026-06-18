const CACHE_NAME = 'kljb-v2';

const STATIC_ASSETS = [
    '/static/css/style.css',
    '/static/manifest.json',
    '/static/icons/icon-192.png',
    '/static/icons/icon-512.png',
    '/static/js/lucide.min.js'
];

// Installation: statische Assets cachen
self.addEventListener('install', e => {
    e.waitUntil(
        caches.open(CACHE_NAME).then(cache => cache.addAll(STATIC_ASSETS))
    );
    self.skipWaiting();
});

// Aktivierung: alten Cache löschen
self.addEventListener('activate', e => {
    e.waitUntil(
        caches.keys().then(keys =>
            Promise.all(keys.filter(k => k !== CACHE_NAME).map(k => caches.delete(k)))
        )
    );
    self.clients.claim();
});

self.addEventListener('push', e => {
    let data = {};
    if (e.data) {
        try { data = e.data.json(); } catch { data = { title: e.data.text() }; }
    }
    e.waitUntil(self.registration.showNotification(data.title || 'KLJB Litzendorf', {
        body: data.body || '',
        icon: '/static/icons/icon-192.png',
        badge: '/static/icons/icon-192.png',
        data: { url: data.url || '/' }
    }));
});

self.addEventListener('notificationclick', e => {
    e.notification.close();
    e.waitUntil(clients.openWindow(e.notification.data.url));
});

// Fetch: Nur statische Assets cachen – alle anderen Requests direkt durchleiten
self.addEventListener('fetch', e => {
    if (e.request.method !== 'GET') return;
    const url = new URL(e.request.url);
    if (!url.pathname.startsWith('/static/')) return;

    e.respondWith(
        fetch(e.request)
            .then(response => {
                const copy = response.clone();
                caches.open(CACHE_NAME).then(cache => cache.put(e.request, copy));
                return response;
            })
            .catch(() => caches.match(e.request))
    );
});
