// Lagos Island's service worker: keeps the game on the device so it opens at once and loads nothing twice.
//  - the page: from the network when it answers within 2.5 s (updates show straight away); on a slow connection the copy
//    on the device opens instead while the new one downloads in the background (the update banner offers it)
//  - models, textures, icons and three.js: from the device once downloaded (cache first)
//  - the game server (accounts, wallet, jobs, who's around): always live, never cached
// "Install app" asks it to download everything listed in precache.json, reporting progress back.
const CACHE = 'lagos-island-v6';
const ASSET = /\.(glb|gltf|bin|jpg|jpeg|png|webp|webmanifest)$/i;
const CDN = /^https:\/\/(cdn\.jsdelivr\.net|fonts\.(googleapis|gstatic)\.com)\//;

self.addEventListener('install', () => self.skipWaiting());
self.addEventListener('activate', (e) => e.waitUntil((async () => {
  const had = (await caches.keys()).some((k) => k !== CACHE); // an older version was on this device
  for (const k of await caches.keys()) if (k !== CACHE) await caches.delete(k);
  await self.clients.claim();
  // any game still open from an older copy reloads into this version (an old page can't always tell it's old)
  if (had) for (const c of await self.clients.matchAll({ type: 'window' })) { try { await c.navigate(c.url); } catch {} }
})()));

self.addEventListener('fetch', (e) => {
  const req = e.request;
  if (req.method !== 'GET') return;
  const url = new URL(req.url);
  const same = url.origin === self.location.origin;
  // only the game's own page is kept on the device; any other page (the payout terms) goes straight to the network, so
  // Safari never gets a redirect from here (it refuses those: 'Response served by service worker has redirections')
  const game = url.pathname === '/' || url.pathname.endsWith('/index.html') || /\/lagos-island\/?$/.test(url.pathname);
  if (same && !game && (req.mode === 'navigate' || url.pathname.endsWith('.html'))) return;
  if (same && (req.mode === 'navigate' || url.pathname.endsWith('/') || url.pathname.endsWith('.html'))) {
    e.respondWith((async () => {
      const net = fetch(req).then(async (r) => { if (r.redirected) r = new Response(await r.blob(), { status: r.status, statusText: r.statusText, headers: r.headers }); if (r.ok) (await caches.open(CACHE)).put(req, r.clone()); return r; }); // a redirect is passed on as a plain page
      e.waitUntil(net.catch(() => {}));
      const saved = (await caches.match(req)) || (await caches.match('./'));
      if (!saved) { try { return await net; } catch { return Response.error(); } }
      const slow = new Promise((ok) => setTimeout(() => ok(null), 2500));
      const first = await Promise.race([net, slow]).catch(() => null);
      if (first && first.ok) return first;
      // the saved copy opened: when the new one has arrived, tell that page so it can offer the update
      e.waitUntil(net.then(async (r) => { if (!r.ok) return; const c = await self.clients.get(e.resultingClientId || e.clientId); if (c) c.postMessage({ type: 'fresh-ready' }); }).catch(() => {}));
      return saved;
    })());
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

// web push: the game server wakes this phone when something happens while the game is closed. The push carries no
// content (nothing for anyone in between to read): the notification says something's new, and the game shows what.
self.addEventListener('push', (e) => {
  e.waitUntil((async () => {
    const open = (await self.clients.matchAll({ type: 'window', includeUncontrolled: true })).some((c) => c.visibilityState === 'visible');
    if (open) return; // the game is in front: it shows its own alert
    await self.registration.showNotification('Lagos Island', { body: 'You have a new message or friend update 💬 Tap to open.', icon: 'icon-192.png', badge: 'icon-192.png', tag: 'li-activity', renotify: true, data: { url: './' } });
  })());
});
self.addEventListener('notificationclick', (e) => {
  e.notification.close();
  e.waitUntil((async () => {
    const all = await self.clients.matchAll({ type: 'window', includeUncontrolled: true });
    for (const c of all) { if ('focus' in c) { await c.focus(); c.postMessage({ type: 'open-phone' }); return; } }
    await self.clients.openWindow('./?from=push');
  })());
});
