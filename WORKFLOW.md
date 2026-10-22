# Working on Lagos Island (any computer)

Before you start: `git pull` in `lagos-island`, `wyrd_serverpod` and `WYRD` (consciousness-bot). When you stop: commit and push.
Work on one computer at a time.

## Where the code lives
- `lagos-island` is the source of truth: `web/index.html` (the game) and `server/lib/island/*.dart`.
- Copy the island server files into `wyrd_serverpod/wyrd/wyrd_server/lib/src/island/`, and `web/index.html` to
  `wyrd_server/web/pages/lagos-island.html`. The rewards module (real-naira gigs, withdrawals) lives only in
  `wyrd_server/lib/src/rewards/`.
- `server/lib/island/island_newtown.dart` is generated from the New Town register in `web/index.html`; regenerate it
  if the reclaimed land's tiles change.

## Deploy (server first, then the site)
1. In `wyrd_server`: `serverpod generate`, `dart analyze lib/src/island lib/src/rewards` (no errors), then
   `scloud deploy` (about 8 minutes). New models need `serverpod create-migration` first.
2. In `lagos-island/cloudflare`: `npm run deploy` (stamps the build, minifies, deploys to play.lagos-island.workers.dev).
3. Commit the stamped `web/version.json` and `web/index.html`.

You need Dart + Serverpod, Node, and to be logged in to `scloud` and `wrangler` on the new computer.
Secrets (Flutterwave keys etc.) live in Serverpod Cloud, never in the repo.

## Gotchas
- Dart strings in single quotes can't hold an apostrophe: reword ("cannot", "do not").
- Game naira (G₦) never leaves the game; only Real ₦ gigs (rewards module) pay withdrawable money.
