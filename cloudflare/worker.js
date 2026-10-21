// Lagos Island on Cloudflare: the game's files, plus one job the game server hands over: sending web push.
//
// POST /push (only from the game server, with PUSH_SECRET): wake one player's phone. The push carries no content at
// all (nothing to encrypt, nothing for the push service to read); the service worker on the phone shows a plain
// "something new" notification, and the game fetches the real thing when it opens. The request is signed with the
// game's VAPID key (ES256), so push services know it's from Lagos Island.
// Every other request is the game's files, as before.

const PUBLIC_KEY = 'BA6OYiZS2uy2fjNIw51NhMS-rsrSdgbxsPgrvlITDkt--AePVBaEeyxJUy7XxzTLS58FOxitbOyBXhPGtSyp5cY';
const b64u = (buf) => btoa(String.fromCharCode(...new Uint8Array(buf))).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
const enc = new TextEncoder();
let signKey = null;

async function vapidHeader(env, endpoint) {
  if (!signKey) signKey = await crypto.subtle.importKey('jwk', JSON.parse(env.VAPID_PRIVATE_JWK), { name: 'ECDSA', namedCurve: 'P-256' }, false, ['sign']);
  const head = b64u(enc.encode(JSON.stringify({ typ: 'JWT', alg: 'ES256' })));
  const body = b64u(enc.encode(JSON.stringify({ aud: new URL(endpoint).origin, exp: Math.floor(Date.now() / 1000) + 12 * 3600, sub: 'https://play.lagos-island.workers.dev' })));
  const sig = await crypto.subtle.sign({ name: 'ECDSA', hash: 'SHA-256' }, signKey, enc.encode(head + '.' + body));
  return `vapid t=${head}.${body}.${b64u(sig)}, k=${PUBLIC_KEY}`;
}

// only the push services browsers use
const PUSH_HOST = /^(fcm\.googleapis\.com|android\.googleapis\.com|updates\.push\.services\.mozilla\.com|[a-z0-9.-]+\.push\.apple\.com|[a-z0-9.-]+\.notify\.windows\.com)$/;

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    if (url.pathname === '/push') {
      if (request.method !== 'POST' || !env.PUSH_SECRET || request.headers.get('x-push-secret') !== env.PUSH_SECRET) return new Response('no', { status: 401 });
      let j; try { j = await request.json(); } catch { return new Response('bad', { status: 400 }); }
      let ep; try { ep = new URL(j.endpoint); } catch { return new Response('bad endpoint', { status: 400 }); }
      if (ep.protocol !== 'https:' || !PUSH_HOST.test(ep.hostname)) return new Response('not a push service', { status: 400 });
      const r = await fetch(ep.href, { method: 'POST', headers: { Authorization: await vapidHeader(env, ep.href), TTL: String(Math.min(86400, Math.max(60, j.ttl | 0 || 3600))), Urgency: 'high', 'Content-Length': '0' } });
      return Response.json({ status: r.status });
    }
    return env.ASSETS.fetch(request);
  },
};
