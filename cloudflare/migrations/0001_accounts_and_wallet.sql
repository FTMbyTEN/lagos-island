-- Lagos Island's own database, step 2 of docs/standalone-server-plan.md: accounts and the G₦ wallet.
-- Nothing reads or writes here yet. Each account is copied over from WYRD the first time its player signs in,
-- after a backup of WYRD's database.

-- a player: their island name, and the WYRD account it was copied from
CREATE TABLE players (
  id TEXT PRIMARY KEY,               -- the game's own id
  handle TEXT NOT NULL UNIQUE COLLATE NOCASE,
  wyrd_user TEXT UNIQUE,             -- WYRD's auth user id, while accounts are still being copied over
  ghost INTEGER NOT NULL DEFAULT 0,  -- seen as "Anonymous"
  created_at INTEGER NOT NULL,       -- unix seconds
  copied_at INTEGER                  -- when the account came over from WYRD
);

-- the G₦ wallet as a ledger: every movement a row, never edited. The balance is the sum.
-- ref makes a movement happen once only (a shift's pay, a purchase), however many times it's sent
CREATE TABLE ledger (
  seq INTEGER PRIMARY KEY AUTOINCREMENT,
  player TEXT NOT NULL REFERENCES players(id),
  delta INTEGER NOT NULL,            -- G₦, whole naira: + in, - out
  reason TEXT NOT NULL,              -- 'opening', 'shift', 'fuel', 'transfer', ...
  ref TEXT NOT NULL UNIQUE,
  at INTEGER NOT NULL
);
CREATE INDEX ledger_player ON ledger(player, seq);

CREATE VIEW balances AS SELECT player, SUM(delta) AS naira FROM ledger GROUP BY player;
