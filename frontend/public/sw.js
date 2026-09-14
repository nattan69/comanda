/**
 * Service Worker de la Comandera (PWA).
 * Objectiu: que l'app arrenqui encara que la xarxa vagi malament al restaurant.
 *
 * Estratègia deliberadament CONSERVADORA i segura per a un TPV:
 *  - MAI cacheja les crides a l'API (vendes/taules han de ser sempre fresques)
 *  - Només cacheja l'«app shell» (HTML/pàgina i assets estàtics)
 *  - Si no hi ha xarxa i no hi ha caché → deixa passar l'error (no inventa dades)
 *
 * ⚠️ Per això NO fem "offline-first" de dades: un TPV que ensenya taules
 * desactualitzades és pitjor que un TPV que diu "sense connexió".
 */

const CACHE = 'comandera-shell-v1';
const SHELL = ['/comandera', '/comandera/sala', '/manifest.webmanifest'];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE).then((c) => c.addAll(SHELL)).then(() => self.skipWaiting()),
  );
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((noms) =>
      Promise.all(noms.filter((n) => n !== CACHE).map((n) => caches.delete(n))),
    ).then(() => self.clients.claim()),
  );
});

self.addEventListener('fetch', (event) => {
  const url = new URL(event.request.url);

  // 1) MAI interceptar l'API (ni ws): sempre xarxa directa
  if (url.pathname.startsWith('/api/') || url.pathname.startsWith('/ws')) {
    return;
  }

  // 2) Només GET del mateix origen
  if (event.request.method !== 'GET' || url.origin !== self.location.origin) {
    return;
  }

  // 3) App shell: xarxa primer, caché com a xarxa de seguretat
  event.respondWith(
    fetch(event.request)
      .then((res) => {
        if (res.ok && url.pathname.startsWith('/comandera')) {
          const copia = res.clone();
          caches.open(CACHE).then((c) => c.put(event.request, copia));
        }
        return res;
      })
      .catch(() => caches.match(event.request)),
  );
});