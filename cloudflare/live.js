// Lagos Island live: one WebSocket per player instead of polling. Positions, chat and voice handshakes go through
// here the moment they happen, and only to the people they concern:
// - Positions go to everyone in the same room, or out in the streets within 2,500 units.
// - Chat goes to everyone in the same room, or within 600 units.
// - Voice handshakes go only between two friends, either on the same channel or within 70 units.
//
// It is a Durable Object using the WebSocket Hibernation API. While no one is moving it sleeps and costs nothing.
// Each socket carries its own player (serializeAttachment), so nothing is lost when it wakes.
//
// Who you are comes only from a ticket signed by the game server (IslandEndpoint.liveTicket, HMAC with LIVE_SECRET):
// your id, the name others see, whether it's an account, your handle and your friends' handles. A ticket is good
// for 15 minutes; the page fetches a new one and reconnects before then.
//
// The page sends:
// - {t:'pos', x, z, room, look, color, car}: at most 5 a second while moving, one every 5 s while still.
// - {t:'say', text}
// - {t:'chan', c}: the voice channel it's on, or '' for none.
// - {t:'sig', to, channel, data}: a voice handshake for a friend.
// It gets back:
// - {t:'snap', players, n}: everyone it can see, when it connects.
// - {t:'m', p}: someone moved.
// - {t:'bye', id}
// - {t:'n', n}: how many are on the island.
// - {t:'say', id, name, v, color, text}
// - {t:'sig', from, channel, data}

const NEAR = 2500, HEAR = 600, VOICE_NEAR = 70;
const enc = new TextEncoder();
let hmacKey = null;
const b64uDec = (s) => Uint8Array.from(atob(s.replace(/-/g, '+').replace(/_/g, '/')), (c) => c.charCodeAt(0));

export async function readTicket(env, ticket) {
  const [body, sig] = String(ticket || '').split('.');
  if (!body || !sig || !env.LIVE_SECRET) return null;
  if (!hmacKey) hmacKey = await crypto.subtle.importKey('raw', enc.encode(env.LIVE_SECRET.trim()), { name: 'HMAC', hash: 'SHA-256' }, false, ['verify']);
  let ok = false; try { ok = await crypto.subtle.verify('HMAC', hmacKey, b64uDec(sig), enc.encode(body)); } catch {}
  if (!ok) return null;
  let t; try { t = JSON.parse(new TextDecoder().decode(b64uDec(body))); } catch { return null; }
  if (!t || typeof t.id !== 'string' || !(t.exp > Date.now() / 1000)) return null;
  return { id: t.id, name: String(t.name || 'Lagosian').slice(0, 40), v: !!t.v, h: String(t.h || ''), f: Array.isArray(t.f) ? t.f.map(String).slice(0, 500) : [], exp: t.exp };
}

const clean = (s, n) => String(s ?? '').replace(/[\u0000-\u001f\u007f]/g, ' ').trim().slice(0, n);
const seesEachOther = (a, b, r) => a.room === b.room && (a.room !== '' || Math.hypot(a.x - b.x, a.z - b.z) < r);
const pub = (p) => ({ id: p.id, name: p.name, v: p.v, color: p.color, x: p.room ? Math.round(p.x * 10) / 10 : Math.round(p.x), z: p.room ? Math.round(p.z * 10) / 10 : Math.round(p.z), room: p.room, look: p.look, car: p.car });

export class City {
  constructor(ctx, env) { this.ctx = ctx; this.env = env; }

  async fetch(request) {
    const url = new URL(request.url);
    if (url.pathname.endsWith('/count')) return Response.json({ n: this.players().length });
    if (request.headers.get('Upgrade') !== 'websocket') return new Response('websocket only', { status: 426 });
    const me = await readTicket(this.env, url.searchParams.get('ticket'));
    if (!me) return new Response('bad ticket', { status: 401 });
    for (const ws of this.ctx.getWebSockets()) { const o = ws.deserializeAttachment(); if (o && o.id === me.id) { try { ws.close(4000, 'signed in elsewhere'); } catch {} } } // (one connection per player)
    const [client, server] = Object.values(new WebSocketPair());
    this.ctx.acceptWebSocket(server);
    server.serializeAttachment({ ...me, x: 0, z: 0, room: '', look: '', color: '#C4572E', car: '', chan: '', said: 0, placed: false });
    return new Response(null, { status: 101, webSocket: client });
  }

  players() { return this.ctx.getWebSockets().map((ws) => [ws, ws.deserializeAttachment()]).filter(([, p]) => p && p.placed); }
  send(ws, o) { try { ws.send(JSON.stringify(o)); } catch {} }
  count() { const n = this.players().length; for (const [ws] of this.players()) this.send(ws, { t: 'n', n }); }

  async webSocketMessage(ws, raw) {
    let m; try { m = JSON.parse(raw); } catch { return; }
    const me = ws.deserializeAttachment(); if (!me) return;
    if (me.exp < Date.now() / 1000 - 60) { ws.close(4001, 'ticket expired'); return; }
    if (m.t === 'pos') {
      const x = +m.x, z = +m.z; if (!Number.isFinite(x) || !Number.isFinite(z)) return;
      const was = { ...me }, first = !me.placed;
      Object.assign(me, { x: Math.max(-60000, Math.min(60000, x)), z: Math.max(-60000, Math.min(60000, z)), room: clean(m.room, 40),
        look: /^[a-z0-9_,|.+-]{0,240}$/.test(m.look || '') ? m.look : '', color: /^#[0-9a-fA-F]{6}$/.test(m.color || '') ? m.color : '#C4572E',
        car: /^[a-z]{2,16}:#[0-9A-Fa-f]{6}$/.test(m.car || '') ? m.car : '', placed: true });
      ws.serializeAttachment(me);
      const all = this.players(), mine = pub(me);
      for (const [o, p] of all) { if (o === ws) continue;
        if (seesEachOther(me, p, NEAR)) this.send(o, { t: 'm', p: mine });
        else if (!first && seesEachOther(was, p, NEAR)) this.send(o, { t: 'bye', id: me.id }); } // (walked out of their sight, or into a building)
      if (first || was.room !== me.room) this.send(ws, { t: 'snap', n: all.length, players: all.filter(([o, p]) => o !== ws && seesEachOther(me, p, NEAR)).slice(0, 80).map(([, p]) => pub(p)) });
      if (first) this.count();
    } else if (m.t === 'say') {
      const text = clean(m.text, 140), now = Date.now(); if (!text || now - me.said < 800 || !me.placed) return;
      me.said = now; ws.serializeAttachment(me);
      const line = { t: 'say', id: me.id, name: me.name, v: me.v, color: me.color, text };
      for (const [o, p] of this.players()) if (o === ws || seesEachOther(me, p, HEAR)) this.send(o, line);
    } else if (m.t === 'chan') {
      me.chan = clean(m.c, 60); ws.serializeAttachment(me);
    } else if (m.t === 'sig') {
      const to = clean(m.to, 40).toLowerCase(), data = String(m.data || ''); if (!me.h || !to || data.length > 16000) return;
      const channel = clean(m.channel, 60);
      for (const [o, p] of this.players()) {
        if (p.h !== to || !me.f.includes(to) || !p.f.includes(me.h)) continue; // (friends both ways, as the game server checks)
        const ok = channel ? me.chan === channel && p.chan === channel : me.room === '' && p.room === '' && Math.hypot(me.x - p.x, me.z - p.z) <= VOICE_NEAR;
        if (ok) this.send(o, { t: 'sig', from: me.h, channel, data });
      }
    }
  }

  async webSocketClose(ws) { this.gone(ws); }
  async webSocketError(ws) { this.gone(ws); }
  gone(ws) {
    const me = ws.deserializeAttachment(); if (!me || !me.placed) return;
    ws.serializeAttachment({ ...me, placed: false });
    for (const [o, p] of this.players()) if (o !== ws && seesEachOther(me, p, NEAR)) this.send(o, { t: 'bye', id: me.id });
    this.count();
  }
}
