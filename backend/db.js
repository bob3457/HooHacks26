// ─── AgriSignal Database Layer ────────────────────────────────────────────────
// SQLite via better-sqlite3 (synchronous — simpler and safe for single-server use)

const Database = require("better-sqlite3");
const path = require("path");

const db = new Database(path.join(__dirname, "agrisignal.db"));

// ── Schema ────────────────────────────────────────────────────────────────────

db.exec(`
  PRAGMA journal_mode = WAL;

  -- Users: email is the primary key, stored exactly as entered (case-sensitive)
  CREATE TABLE IF NOT EXISTS users (
    email      TEXT    PRIMARY KEY,   -- SQLite TEXT = uses case-sensitive by default
    created_at TEXT    NOT NULL DEFAULT (datetime('now'))
  );

  -- Farmer profile: one row per user, tracks which input mode they used last
  CREATE TABLE IF NOT EXISTS farmer_profiles (
    email          TEXT    PRIMARY KEY REFERENCES users(email),
    input_mode     TEXT    NOT NULL CHECK(input_mode IN ('direct','crops')),
    fertilizer_lbs REAL,
    updated_at     TEXT    NOT NULL DEFAULT (datetime('now'))
  );

  -- Crop rows: many per user (replaced on each save)
  CREATE TABLE IF NOT EXISTS farmer_crops (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    email      TEXT    NOT NULL REFERENCES users(email),
    crop_type  TEXT    NOT NULL,
    acres      REAL    NOT NULL
  );
`);

// ── Prepared statements ───────────────────────────────────────────────────────

const stmts = {
  // Users
  findUser:   db.prepare("SELECT email, created_at FROM users WHERE email = ?"),
  createUser: db.prepare("INSERT INTO users (email) VALUES (?)"),

  // Profile
  getProfile: db.prepare(`
    SELECT fp.email, fp.input_mode, fp.fertilizer_lbs, fp.updated_at
    FROM farmer_profiles fp WHERE fp.email = ?
  `),
  upsertProfile: db.prepare(`
    INSERT INTO farmer_profiles (email, input_mode, fertilizer_lbs, updated_at)
    VALUES (?, ?, ?, datetime('now'))
    ON CONFLICT(email) DO UPDATE SET
      input_mode     = excluded.input_mode,
      fertilizer_lbs = excluded.fertilizer_lbs,
      updated_at     = excluded.updated_at
  `),

  // Crops
  getCrops:      db.prepare("SELECT crop_type, acres FROM farmer_crops WHERE email = ? ORDER BY id"),
  deleteCrops:   db.prepare("DELETE FROM farmer_crops WHERE email = ?"),
  insertCrop:    db.prepare("INSERT INTO farmer_crops (email, crop_type, acres) VALUES (?, ?, ?)"),
};

// ── Transactions ──────────────────────────────────────────────────────────────

const saveProfileTx = db.transaction((email, inputMode, fertilizerLbs, crops) => {
  stmts.upsertProfile.run(email, inputMode, fertilizerLbs ?? null);
  stmts.deleteCrops.run(email);
  for (const c of (crops || [])) {
    stmts.insertCrop.run(email, c.type, c.acres);
  }
});

// ── Exported API ──────────────────────────────────────────────────────────────

module.exports = {
  // Returns the user row or null. Email match is exact (case-sensitive).
  findUser(email) {
    return stmts.findUser.get(email) ?? null;
  },

  // Creates user if not already present. Returns the user row.
  loginOrCreate(email) {
    let user = stmts.findUser.get(email);
    if (!user) {
      stmts.createUser.run(email);
      user = stmts.findUser.get(email);
    }
    return user;
  },

  // Returns full profile + crops, or null if nothing saved yet.
  getProfile(email) {
    const profile = stmts.getProfile.get(email);
    if (!profile) return null;
    const crops = stmts.getCrops.all(email).map(c => ({ type: c.crop_type, acres: c.acres }));
    return {
      email:         profile.email,
      inputMode:     profile.input_mode,
      fertilizerLbs: profile.fertilizer_lbs,
      updatedAt:     profile.updated_at,
      crops,
    };
  },

  // Persists profile atomically (crops are fully replaced each save).
  saveProfile(email, { inputMode, fertilizerLbs, crops }) {
    saveProfileTx(email, inputMode, fertilizerLbs, crops);
    return module.exports.getProfile(email);
  },
};
