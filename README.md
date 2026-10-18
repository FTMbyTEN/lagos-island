# Lagos Island

A multiplayer game of Lagos Island, Ikoyi, Victoria Island, Eko Atlantic, Lekki, Ajah and Ilashe, drawn as a little game town in the browser. It's one HTML page with a canvas: no game engine and no build step. It runs on phones and on PC.

**Play:** https://wryd00.serverpod.space/lagos-island

## What's in it

- **The board:** the island's districts as blocks of land in the lagoon, joined by bridges and the Lagos–Calabar Coastal Road.
  - Each landmark is its own small model: the Central Mosque, Balogun Market, the Oba's palace, Tafawa Balewa Square, the Marina towers, Eko Hotel, the Eko Atlantic skyline, the Lekki Toll Gate and the Lekki Conservation Centre.
  - There's also a refinery, two clubs, a casino, the arena, WYRD Tower, an airport, the Blue Line station, Ad Island's digital billboards, HQ Row and reclaimed land.
  - Each district has its own camera angle, and the island follows Lagos time, with night lighting.
- **One account with WYRD:** sign up at the door with an email, a username and a password. The same account works in the WYRD app.
- **Inside buildings:** apartments (HQs), clubs, the casino, WYRD Tower, the arena, the car dealers and the Eko Home Store have rooms you walk around in. Owners arrange their home's furniture.
- **Homes:** everyone gets a free BQ on HQ Row. Six estates have plots to buy: mini flats and bungalows in Ajah, terraces and duplexes in Lekki, townhouses, lofts and mansions in Ikoyi, villas on Banana Island. A loft keeps your cars inside.
- **People and fashion:** everyone is a 3D person (Quaternius, CC0) who walks, runs, sits, dances and swims. Pick your body, skin, hair and a free outfit at sign-up; buy outfits from Nike and Adidas to Gucci, Fendi and Mai Atafo bespoke at the Idumota, Falomo and Circle Mall boutiques or on the Fashion app, and change at home from your wardrobe. Brand names only, not affiliated.
- **House parties:** throw one at any home you own (Afrobeats night, Amapiano or an Owambe with naira raining down), open to all or invite only. Inside: lights, a disco ball, confetti. Outside: the house lights up so people see it. Invited friends get it on their phones and can go straight there.
- **Banana Island Marina:** yacht charters. A free harbour tour, a lagoon cruise, a sunset party with a DJ, or a private charter: you're on deck while the lagoon and the skyline go by, and back at the marina when it's over.
- **Eko Home Store:** 76 real 3D pieces of furniture (Kenney's Furniture Kit, CC0) from ₦2,000 to ₦1.5M. Homes come empty; you place what you buy.
  - Your own HQ is always open to you. Anyone else knocks, and the owner lets them in from their phone.
- **The phone (WYRD OS):**
  - **Wallet:** naira earned from shifts, paid at Lagos rates.
  - **Jobs:** real employers post jobs, which are checked before they show.
  - **Link:** end-to-end encrypted private conversations and groups.
  - **My HQ** and **Arena:** tickets for live shows.
  - **Casino:** play money.
  - **Ride:** Uber-style okada and car trips, paid on arrival.
  - **WYRD:** the AI that runs the island.
- **WYRD:** WYRD Tower is where you talk to WYRD itself. It never sees your Link messages.

## The code

```
web/index.html            the whole game: page, canvas renderer, phone OS
server/lib/island/        the server side (Serverpod 4, Dart)
  island_endpoint.dart        who's where, live (no account needed)
  island_auth_endpoint.dart   sign up / sign in, one account with WYRD
  island_me_endpoint.dart     the phone: wallet, jobs, Link, HQs, rooms, arena, casino, rides, WYRD
  *.spy.yaml                  the data models (Serverpod generates the Dart and the tables)
server/migrations/        the SQL that makes the island's tables
```

## How it runs today

The game is served by the WYRD Serverpod server and shares its database, accounts and naira ledger.

- **Served page:** the server serves `web/index.html` at `/lagos-island`.
- **API calls:** the page calls the API at the same host with `.api.` added (`https://<project>.api.serverpod.space`). Add `?api=<url>` to point it at another server.
- **Copying the server code into a Serverpod project:** put `server/lib/island/` under `lib/src/island/`, run `serverpod generate` and `serverpod create-migration`, and serve the page:

  ```dart
  pod.webServer.addRoute(StaticRoute.file(File('web/pages/lagos-island.html')), '/lagos-island');
  ```

  The Eko Home Store and buyable homes add two tables (`island_furniture`, `island_home`), so after copying run `serverpod generate` and `serverpod create-migration`, apply the migration, and redeploy. Until then the store and the homes show in the game, and buying says they open when the server update goes live.

  It relies on parts of WYRD that this repo doesn't include:
  - the email sign-in provider (`serverpod_auth_idp_server`);
  - the naira ledger (`Bank`, `WorldAuthority.citizen`);
  - the operator check (`DroneService.isOperator`).

Handy links: `?night=1` forces night lighting; `?at=column,row` starts the view at a spot (for example `?at=56,24` for the airport).

## Privacy

- **Link:** messages and group names are encrypted in the browser with WebCrypto (ECDH P-256 and AES-GCM). The server only stores scrambled text.
- **Job matching:** happens only for players who choose "open to work", and only they see the ranking.
- **Employers:** see only an applicant's username, skills and note.
- **HQs:** invite-only.
