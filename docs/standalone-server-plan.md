# Lagos Island's own server, on Cloudflare

Lagos Island runs today inside WYRD's Serverpod server (`wryd00`), sharing its process and database with WYRD's AI jobs.
The audit on 27 Oct 2026 (30 minutes of live logs) showed why the game feels slow:

| What | Calls | Average | Worst |
|---|---|---|---|
| `inbox` (messages) | 83 | 2.1 s | 5.1 s |
| `friends` | 16 | 1.4 s | 2.1 s |
| `hqRow`, `homes`, `housing`, `shows` | — | 1.1–1.7 s | — |
| `login` | 1 | 17 s | 17 s |
| WYRD's Lexicon / SelfQuestion / Feed ticks (same server) | — | 4–12 s | 12.9 s |

A one-query call takes over a second because the game queues behind WYRD's background work. The client-side polling
was cut on 27 Oct (inbox every 60 s instead of 6 s, presence only when someone's in sight); the rest needs a server of
the game's own.

## The shape

```
play.lagos-island.workers.dev
 ├─ static site (as now: page, map, models, textures)
 ├─ Worker  /api/*         accounts, wallet, homes, jobs, shops (stateless, D1)
 └─ Durable Objects
     ├─ City cell × N      live presence, chat, voice handshakes for one area of the map (WebSocket)
     ├─ Room × N           a club, an HQ, a party: who's in, the DJ deck, the dance floor
     └─ Player × 1 each    wake line, inbox, friends' signals (replaces long-polling)
 D1 (SQLite)               the 22 tables, game data only
 R2                        player uploads (photos, room shots)
```

- **WebSockets instead of polling.** One socket per player to its city cell. Positions go out 5–10 times a second to the
  people who can see you, nothing to those who can't. Presence, chat, voice handshakes and wake-ups all ride it:
  no `tick`, `wake`, `inbox` or `voiceInbox` round trips at all.
- **The city is split into cells** (about 1 km squares). Each is its own Durable Object, close to its players, so a busy
  Lekki doesn't slow Ikoyi. A player belongs to the cell they stand in and hears the neighbouring ones.
- **One read on login, then deltas.** The ~25 calls the game makes when it starts become one `bootstrap` call
  returning everything the phone apps need, and changes push over the socket after that.
- **D1 for the rest**: wallet, homes, cars, furniture, jobs, careers, shows, tickets. Every query indexed; nothing
  scans a table on a hot path.

## What moves, and what stays with WYRD

| Part | Today | After |
|---|---|---|
| Accounts and sign-in | Serverpod auth (WYRD's users) | The game's own: email or phone + password (hashed), sessions in KV. Existing players sign in with the same details once; their account is copied over the first time. |
| Game naira (G₦) wallet | `world/bank.dart` in WYRD | D1 ledger, every movement a row (as now: G₦ never leaves the game) |
| Real-naira gigs, withdrawals, Flutterwave top-ups | WYRD's rewards module | **Stays with WYRD** (it's real money and its compliance lives there). The game calls a small signed API on WYRD for these; WYRD's Flutterwave webhook keeps working. |
| WYRD the character (chat, tower) | WYRD | Stays with WYRD; the game calls it over HTTPS when you talk to WYRD |
| Drones, world authority | WYRD | Whatever the game uses is copied into the game server; the rest stays |
| Everything else (homes, cars, HQ Row, New Town, jobs, careers, grid shifts, clubs, parties, voice, stops) | Serverpod | Cloudflare |

## Moving over without losing anyone's things

1. **Export.** A one-off script reads every island table from WYRD's Postgres and writes D1 SQL.
2. **Dual-read period (a week).** The new server is live; sign-in on it copies an account over from WYRD (by a signed
   lookup) the first time. Balances, homes and cars come across in the same step.
3. **Switch.** The game points at the new API. WYRD's island endpoints answer with "moved" for a month, then go.
4. **Check.** Totals (players, G₦ in circulation, homes, cars, flats) compared before and after; any difference stops
   the switch.

## Order of work

1. City cells and sockets (presence, chat, voice): the biggest smoothness win. Runs alongside the old server; the game
   uses it when it's there.
2. Accounts and the wallet on D1, with the copy-on-first-sign-in.
3. Homes, cars, furniture, HQ Row, New Town, jobs, careers, shows, parties: endpoint by endpoint, each with its tests.
4. The WYRD bridge for real-naira gigs and WYRD chat.
5. Export, dual-read week, switch, check.

## What it costs and needs

- It starts on Cloudflare's free plan: SQLite-backed Durable Objects, D1 and R2 are all available there. Workers
  Paid ($5 a month) comes later, when the daily limits get close (many players on at once for hours).
- From you: the Workers Paid plan switched on in the dashboard, and a D1 database created (or permission for me to
  create it with `wrangler`).
- Before step 5: a backup of WYRD's database.

## What "done" looks like

- Any game call under 100 ms at the 95th percentile; positions updating 5–10 times a second for people in sight.
- 100 players on the island at once with no slowdown; WYRD's AI jobs no longer touch the game at all.
- Every existing player's account, G₦, homes, cars and flats on the new server, totals matching.

## Progress

- **Step 1, done (27 Oct 2026).** The live server is up: `cloudflare/live.js`, with tickets from `IslandEndpoint.liveTicket`.
  The game uses it for positions, chat and voice handshakes, and falls back to polling without it.
- **Step 2, started.** The game's database `lagos-island` (D1) is created and bound as `DB`, with the accounts and ledger
  tables (`cloudflare/migrations/`). Nothing uses it yet. Copying accounts over waits for a backup of WYRD's database.
