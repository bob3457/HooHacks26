// ─── AgriSignal Backend Server ────────────────────────────────────────────────

const express = require("express");
const cors    = require("cors");
const db      = require("./db");

const app  = express();
const PORT = 8000;

app.use(cors());
app.use(express.json());

// Serve the frontend files (index.html, dashboard.html, css/, js/)
app.use(express.static(__dirname));

// ── Helpers ───────────────────────────────────────────────────────────────────

function ok(res, data)       { res.json(data); }
function err(res, code, msg) { res.status(code).json({ error: msg }); }

// Validates an email string (basic check, case-sensitive storage)
function isValidEmail(email) {
  return typeof email === "string" && /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);
}

// ── Auth ──────────────────────────────────────────────────────────────────────

// POST /api/auth/login
// Body: { email: string }
// Creates the user row if first time, otherwise returns existing user.
// Email is stored EXACTLY as provided — case-sensitive.
app.post("/api/auth/login", (req, res) => {
  const raw = req.body.email;
  if (!raw || !isValidEmail(raw)) {
    return err(res, 400, "A valid email is required.");
  }
  // Normalize to lowercase — emails are case-insensitive
  const email = raw.trim().toLowerCase();
  try {
    const user = db.loginOrCreate(email);
    ok(res, { email: user.email, createdAt: user.created_at });
  } catch (e) {
    console.error(e);
    err(res, 500, "Database error.");
  }
});

// ── Farmer Profile ────────────────────────────────────────────────────────────

// GET /api/farmer/:email
// Returns saved farm profile + crops, or 404 if nothing saved yet.
app.get("/api/farmer/:email", (req, res) => {
  const email = req.params.email.toLowerCase();

  // Verify the user exists first
  const user = db.findUser(email);
  if (!user) return err(res, 404, "User not found.");

  const profile = db.getProfile(email);
  if (!profile) return err(res, 404, "No profile saved yet.");

  ok(res, profile);
});

// POST /api/farmer/:email
// Body: { inputMode: "direct"|"crops", fertilizerLbs?: number, crops?: [{type,acres}] }
// Replaces (upserts) the entire profile for this user.
app.post("/api/farmer/:email", (req, res) => {
  const email = req.params.email.toLowerCase();
  const { inputMode, fertilizerLbs, crops } = req.body;

  const user = db.findUser(email);
  if (!user) return err(res, 404, "User not found. Log in first.");

  if (!["direct", "crops"].includes(inputMode)) {
    return err(res, 400, "inputMode must be 'direct' or 'crops'.");
  }
  if (inputMode === "direct" && (fertilizerLbs == null || fertilizerLbs <= 0)) {
    return err(res, 400, "fertilizerLbs must be a positive number for direct mode.");
  }
  if (inputMode === "crops" && (!Array.isArray(crops) || crops.length === 0)) {
    return err(res, 400, "crops array is required for crops mode.");
  }

  try {
    const saved = db.saveProfile(email, { inputMode, fertilizerLbs, crops });
    ok(res, { ok: true, profile: saved });
  } catch (e) {
    console.error(e);
    err(res, 500, "Database error.");
  }
});

// ── Price & Forecast (stubs — wire to real data source when ready) ────────────
// These return empty arrays so the frontend loads without crashing.
// Replace the stub bodies with real data queries.

// GET /api/prices/history?commodity=urea&from=YYYY-MM&to=YYYY-MM
// Expected return: { labels: string[], values: number[] }
app.get("/api/prices/history", (req, res) => {
  // TODO: query your price table or read from XLS in /series_data
  ok(res, { labels: [], values: [] });
});

// GET /api/prices/natgas/history?from=YYYY-MM&to=YYYY-MM
// Expected return: { labels: string[], values: number[] }
app.get("/api/prices/natgas/history", (req, res) => {
  // TODO: query Henry Hub data from /series_data/NG_SUM_LSUM_DCU_NUS_M.xls
  ok(res, { labels: [], values: [] });
});

// GET /api/prices/forecast?commodity=urea&days=90
// Expected return: { labels: string[], mean: number[], low: number[], high: number[] }
app.get("/api/prices/forecast", (req, res) => {
  // TODO: run forecasting model and return results
  ok(res, { labels: [], mean: [], low: [], high: [] });
});

// ── Buy Signal (stub) ─────────────────────────────────────────────────────────

// GET /api/signal/buy-timing?tonsNeeded=X
// Expected return: { urgency, recommendation, rationale, bestMonth, bestPrice, currentPrice }
app.get("/api/signal/buy-timing", (req, res) => {
  // TODO: compute signal from forecast model output
  ok(res, {
    urgency:        "MODERATE",
    recommendation: "Signal not yet available — connect forecast model.",
    rationale:      "The forecasting backend is not yet connected. Once price data is loaded and the model is running, this will show a personalized buy-timing recommendation.",
    bestMonth:      "—",
    bestPrice:      null,
    currentPrice:   null,
  });
});

// ── Exposure Calculator (stub) ────────────────────────────────────────────────

// POST /api/exposure/calculate
// Body: { inputMode, fertilizerLbs?, crops?, forecastDays? }
// Expected return: { tonsUreaNeeded, totalLbsN, costByMonth, breakdown }
app.post("/api/exposure/calculate", (req, res) => {
  // TODO: implement full exposure calculation once price forecast is available
  ok(res, {
    tonsUreaNeeded: null,
    totalLbsN:      null,
    costByMonth:    [],
    breakdown:      [],
  });
});

// ── Start ─────────────────────────────────────────────────────────────────────

app.listen(PORT, () => {
  console.log(`AgriSignal running at http://localhost:${PORT}`);
  console.log(`Database: agrisignal.db`);
});
