// ─── AgriSignal Backend Server ────────────────────────────────────────────────

const express = require("express");
const cors    = require("cors");
const path    = require("path");
const fs      = require("fs");
const db      = require("./db");

const app      = express();
const PORT     = 8000;
const CACHE    = path.join(__dirname, "../data/processed/cache.json");

app.use(cors());
app.use(express.json());

// Serve the frontend files (index.html, dashboard.html, css/, js/)
app.use(express.static(path.join(__dirname, "../frontend")));

// ── Cache loader ──────────────────────────────────────────────────────────────
// Reads data/processed/cache.json (written by run_pipeline.py).
// Returns null if the file doesn't exist yet.

let _cache = null;

function loadCache() {
  try {
    const raw = fs.readFileSync(CACHE, "utf8");
    _cache = JSON.parse(raw);
  } catch {
    _cache = null;
  }
  return _cache;
}

function getCache() {
  // Re-read on every request so a fresh pipeline run is picked up without restart
  return loadCache();
}

// ── Helpers ───────────────────────────────────────────────────────────────────

function ok(res, data)       { res.json(data); }
function err(res, code, msg) { res.status(code).json({ error: msg }); }

function isValidEmail(email) {
  return typeof email === "string" && /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);
}

// ── Exposure calculator constants (per spec §8.5) ─────────────────────────────
// Nitrogen application rates in lbs N per harvested acre (USDA ERS hardcoded values)

const NITROGEN_INTENSITY = {
  corn:      150,
  wheat:      90,
  cotton:     80,
  sorghum:    80,
  rice:       95,
  soybeans:    5,
  hay:        20,
  livestock:   0,
  other:      60,
};

const UREA_N_CONTENT = 0.46;   // 46% nitrogen by weight
const LBS_PER_MT     = 2204.6; // lbs per metric ton

// Sensitivity labels for crop breakdown display
const SENSITIVITY_LABEL = {
  corn: "Very high", wheat: "High", cotton: "High", sorghum: "Moderate-high",
  rice: "High", soybeans: "Very low", hay: "Low", livestock: "None", other: "Moderate",
};

function ureaCostPerAcre(crop, ureaPricePerMt) {
  const lbsN = NITROGEN_INTENSITY[crop] ?? NITROGEN_INTENSITY.other;
  if (lbsN === 0) return 0;
  const mtUrea = (lbsN / UREA_N_CONTENT) / LBS_PER_MT;
  return mtUrea * ureaPricePerMt;
}

function totalLbsN(crop, acres) {
  return (NITROGEN_INTENSITY[crop] ?? NITROGEN_INTENSITY.other) * acres;
}

function tonsUreaNeeded(lbsN) {
  return (lbsN / UREA_N_CONTENT) / LBS_PER_MT;
}

// ── Auth ──────────────────────────────────────────────────────────────────────

app.post("/api/auth/login", (req, res) => {
  const raw = req.body.email;
  if (!raw || !isValidEmail(raw)) {
    return err(res, 400, "A valid email is required.");
  }
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

app.get("/api/farmer/:email", (req, res) => {
  const email = req.params.email.toLowerCase();
  const user  = db.findUser(email);
  if (!user) return err(res, 404, "User not found.");

  const profile = db.getProfile(email);
  if (!profile) return err(res, 404, "No profile saved yet.");

  ok(res, profile);
});

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

// ── Price History ─────────────────────────────────────────────────────────────

// GET /api/prices/history?commodity=urea&from=YYYY-MM&to=YYYY-MM
app.get("/api/prices/history", (req, res) => {
  const cache = getCache();
  if (!cache) return ok(res, { labels: [], values: [] });

  const commodity = (req.query.commodity || "urea").toLowerCase();
  const source    = commodity === "urea" ? cache.urea_history : cache.urea_history;

  ok(res, source);
});

// GET /api/prices/natgas/history
app.get("/api/prices/natgas/history", (req, res) => {
  const cache = getCache();
  if (!cache) return ok(res, { labels: [], values: [] });

  ok(res, cache.natgas_history);
});

// ── Forecast ──────────────────────────────────────────────────────────────────

// GET /api/prices/forecast?commodity=urea&days=90
app.get("/api/prices/forecast", (req, res) => {
  const cache = getCache();
  if (!cache) return ok(res, { labels: [], mean: [], low: [], high: [] });

  ok(res, cache.forecast);
});

// ── Buy Signal ────────────────────────────────────────────────────────────────

// GET /api/signal/buy-timing?tonsNeeded=X
app.get("/api/signal/buy-timing", (req, res) => {
  const cache = getCache();
  if (!cache) {
    return ok(res, {
      urgency:        "LOW",
      recommendation: "Model not yet trained",
      rationale:      "Run python backend/train_models.py then python backend/run_pipeline.py to generate forecasts.",
      bestMonth:      "—",
      bestPrice:      null,
      currentPrice:   null,
    });
  }

  ok(res, cache.signal);
});

// ── Monte Carlo ───────────────────────────────────────────────────────────────

// GET /api/monte-carlo
app.get("/api/monte-carlo", (req, res) => {
  const cache = getCache();
  if (!cache) return ok(res, {});

  ok(res, { ...cache.monte_carlo, sim_t2_distribution: cache.sim_t2_distribution });
});

// ── Exposure Calculator ───────────────────────────────────────────────────────

// POST /api/exposure/calculate
// Body: { inputMode: "direct"|"crops", fertilizerLbs?: number, crops?: [{type,acres}] }
app.post("/api/exposure/calculate", (req, res) => {
  const { inputMode, fertilizerLbs, crops } = req.body;
  const cache = getCache();

  // Current and forecast urea prices from cache, or fallback to $350/mt
  const currentPrice  = cache?.signal?.currentPrice  ?? 350;
  const forecastPrices = cache
    ? [cache.signal.forecast_t1, cache.signal.forecast_t2, cache.signal.forecast_t3]
    : [350, 350, 350];
  const forecastLow  = cache
    ? [cache.monte_carlo.p10_t1, cache.monte_carlo.p10_t2, cache.monte_carlo.p10_t3]
    : forecastPrices;
  const forecastHigh = cache
    ? [cache.monte_carlo.p90_t1, cache.monte_carlo.p90_t2, cache.monte_carlo.p90_t3]
    : forecastPrices;
  const monthLabels = cache
    ? cache.forecast.labels
    : ["Next month", "In 2 months", "In 3 months"];

  let totalN  = 0;   // total lbs N
  let breakdown = [];

  if (inputMode === "direct") {
    totalN = fertilizerLbs ?? 0;
  } else if (inputMode === "crops" && Array.isArray(crops)) {
    for (const c of crops) {
      const n   = totalLbsN(c.type, c.acres);
      const sens = SENSITIVITY_LABEL[c.type] ?? "Moderate";
      totalN += n;
      breakdown.push({
        label:       `${c.type.charAt(0).toUpperCase() + c.type.slice(1)} (${c.acres} acres)`,
        acres:       c.acres,
        lbsN:        Math.round(n),
        sensitivity: sens,
      });
    }
  }

  const tonsNeeded = tonsUreaNeeded(totalN);

  // Cost at current price
  const currentCost = tonsNeeded * currentPrice;

  // Cost by forecast month (mean, low, high)
  const costByMonth = monthLabels.map((label, i) => ({
    label,
    cost: Math.round(tonsNeeded * forecastPrices[i]),
    low:  Math.round(tonsNeeded * forecastLow[i]),
    high: Math.round(tonsNeeded * forecastHigh[i]),
  }));

  ok(res, {
    tonsUreaNeeded: Math.round(tonsNeeded * 10) / 10,
    totalLbsN:      Math.round(totalN),
    currentCost:    Math.round(currentCost),
    costByMonth,
    breakdown,
  });
});

// ── Health check ──────────────────────────────────────────────────────────────

app.get("/api/health", (req, res) => {
  const cache = getCache();
  ok(res, {
    status:       "ok",
    modelLoaded:  cache !== null,
    generatedAt:  cache?.generated_at ?? null,
    asOfDate:     cache?.as_of_date   ?? null,
    currentUrea:  cache?.signal?.currentPrice ?? null,
  });
});

// ── Start ─────────────────────────────────────────────────────────────────────

loadCache();

app.listen(PORT, () => {
  console.log(`AgriSignal running at http://localhost:${PORT}`);
  console.log(`Cache: ${_cache ? `loaded (as of ${_cache.as_of_date})` : "not found — run pipeline first"}`);
});
