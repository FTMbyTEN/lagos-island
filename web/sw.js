// Lagos Island's service worker: keeps the game on the device so it opens at once and loads nothing twice.
//  - the page: from the network when there is one (updates show straight away), from the device when offline
//  - models, textures, icons and three.js: from the device once downloaded (cache first)
//  - the game server (accounts, wallet, jobs, who's around): always live, never cached
// "Install app" asks it to download everything listed in precache.json, reporting progress back.
const CACHE = 'lagos-island-v1';
const ASSET = /\.(glb|gltf|bin|jpg|jpeg|png|webp|webmanifest)$/i;
const CDN = /^https:\/\/(cdn\.jsdelivr\.net|fonts\.(googleapis|gstatic)\.com)\//;

self.addEventListener('install', () => self.skipWaiting());
self.addEventListener('activate', (e) => e.waitUntil((async () => {
  for (const k of await caches.keys()) if (k !== CACHE) await caches.delete(k);
  await self.clients.claim();
})()));

self.addEventListener('fetch', (e) => {
  const req = e.request;
  if (req.method !== 'GET') return;
  const url = new URL(req.url);
  const same = url.origin === self.location.origin;
  if (same && (req.mode === 'navigate' || url.pathname.endsWith('/') || url.pathname.endsWith('.html'))) {
    e.respondWith((async () => { try { const r = await fetch(req); if (r.ok) (await caches.open(CACHE)).put(req, r.clone()); return r; } catch { return (await caches.match(req)) || (await caches.match('./')) || Response.error(); } })());
    return;
  }
  if ((same && ASSET.test(url.pathname)) || CDN.test(req.url)) {
    e.respondWith((async () => { const hit = await caches.match(req); if (hit) return hit; const r = await fetch(req); if (r.ok || r.type === 'opaque') (await caches.open(CACHE)).put(req, r.clone()); return r; })());
  }
});

self.addEventListener('message', (e) => {
  if (!e.data || e.data.type !== 'precache' || !e.ports[0]) return;
  const port = e.ports[0];
  e.waitUntil((async () => {
    let list = [];
    try { list = await (await fetch('precache.json', { cache: 'no-store' })).json(); } catch {}
    const cache = await caches.open(CACHE);
    let got = 0;
    const one = async (u) => { try { if (!(await cache.match(u))) { const r = await fetch(u); if (r.ok) await cache.put(u, r); } } catch {} got++; port.postMessage({ got, of: list.length }); };
    for (let i = 0; i < list.length; i += 6) await Promise.all(list.slice(i, i + 6).map(one)); // six at a time
    port.postMessage({ got, of: list.length, ok: true });
  })());
});
