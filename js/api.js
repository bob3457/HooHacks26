// ─── AgriSignal API Client ────────────────────────────────────────────────────
// All backend calls go through this file.
// Set BASE_URL to your server origin when the backend is ready.

const API = {
  BASE_URL: "http://localhost:8000",   // ← change when backend is deployed

  // ── Price & Forecast ──────────────────────────────────────────────────────

  // GET /api/prices/history?commodity=urea&from=YYYY-MM&to=YYYY-MM
  // Returns: { labels: string[], values: number[] }
  async getPriceHistory(commodity = "urea", from = null, to = null) {
    const params = new URLSearchParams({ commodity });
    if (from) params.set("from", from);
    if (to)   params.set("to",   to);
    return this._get(`/api/prices/history?${params}`);
  },

  // GET /api/prices/natgas/history?from=YYYY-MM&to=YYYY-MM
  // Returns: { labels: string[], values: number[] }
  async getNatGasHistory(from = null, to = null) {
    const params = new URLSearchParams();
    if (from) params.set("from", from);
    if (to)   params.set("to",   to);
    return this._get(`/api/prices/natgas/history?${params}`);
  },

  // GET /api/prices/forecast?commodity=urea&days=90
  // Returns: { labels: string[], mean: number[], low: number[], high: number[] }
  async getPriceForecast(commodity = "urea", days = 90) {
    return this._get(`/api/prices/forecast?commodity=${commodity}&days=${days}`);
  },

  // ── Best-Time-to-Buy Signal ───────────────────────────────────────────────

  // GET /api/signal/buy-timing?tonsNeeded=X
  // Returns: { urgency: "HIGH"|"MODERATE"|"LOW", recommendation: string,
  //            rationale: string, bestMonth: string, bestPrice: number,
  //            currentPrice: number }
  async getBuyTiming(tonsNeeded = null) {
    const params = new URLSearchParams();
    if (tonsNeeded !== null) params.set("tonsNeeded", tonsNeeded);
    return this._get(`/api/signal/buy-timing?${params}`);
  },

  // ── Farmer Profile (saved per-email) ─────────────────────────────────────

  // GET /api/farmer/:email
  // Returns: { email, inputMode, fertilizerLbs, crops: [{type,acres}], updatedAt }
  async getFarmerProfile(email) {
    return this._get(`/api/farmer/${encodeURIComponent(email)}`);
  },

  // POST /api/farmer/:email
  // Body: { inputMode: "direct"|"crops", fertilizerLbs?, crops? }
  // Returns: { ok: true, profile }
  async saveFarmerProfile(email, data) {
    return this._post(`/api/farmer/${encodeURIComponent(email)}`, data);
  },

  // ── Exposure Calculator ───────────────────────────────────────────────────

  // POST /api/exposure/calculate
  // Body: { inputMode, fertilizerLbs?, crops?, forecastDays? }
  // Returns: { tonsUreaNeeded, totalCostNow, costByMonth: [{label,cost,low,high}],
  //            breakdown: [{crop,acres,lbsN,sensitivity}] }
  async calculateExposure(payload) {
    return this._post("/api/exposure/calculate", payload);
  },

  // ── Auth ──────────────────────────────────────────────────────────────────

  // POST /api/auth/login
  // Body: { email }   (email is already lowercased by the caller)
  // Returns: { email, createdAt }
  async login(email) {
    return this._post("/api/auth/login", { email });
  },

  // ── Internals ─────────────────────────────────────────────────────────────

  async _get(path) {
    const res = await fetch(this.BASE_URL + path);
    if (!res.ok) throw new Error(`API error ${res.status}: ${path}`);
    return res.json();
  },

  async _post(path, body) {
    const res = await fetch(this.BASE_URL + path, {
      method:  "POST",
      headers: { "Content-Type": "application/json" },
      body:    JSON.stringify(body),
    });
    if (!res.ok) throw new Error(`API error ${res.status}: ${path}`);
    return res.json();
  },
};
