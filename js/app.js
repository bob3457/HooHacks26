// ─── AgriSignal Front-end Application ────────────────────────────────────────

// ── Auth ─────────────────────────────────────────────────────────────────────

function getSession() {
  try { return JSON.parse(sessionStorage.getItem("agrisignal_user")); }
  catch { return null; }
}

function setSession(user) {
  sessionStorage.setItem("agrisignal_user", JSON.stringify(user));
}

function requireAuth() {
  const user = getSession();
  if (!user) { window.location.href = "index.html"; }
  return user;
}

// ── Chart state ──────────────────────────────────────────────────────────────

let priceChart = null;

function renderPriceChart(histLabels, histUrea, histNatGas,
                          forecastLabels, forecastMean, forecastLow, forecastHigh,
                          showNatGas) {
  const ctx = document.getElementById("priceChart").getContext("2d");

  const allLabels = [...histLabels, ...forecastLabels];

  // Pad historical arrays with null for forecast slots
  const ureaHist  = [...histUrea,   ...Array(forecastLabels.length).fill(null)];
  const natGasHist = showNatGas
    ? [...histNatGas, ...Array(forecastLabels.length).fill(null)]
    : null;

  // Pad forecast arrays with null for historical slots
  const fMean  = [...Array(histLabels.length - 1).fill(null), histUrea[histUrea.length - 1], ...forecastMean];
  const fLow   = [...Array(histLabels.length - 1).fill(null), histUrea[histUrea.length - 1], ...forecastLow];
  const fHigh  = [...Array(histLabels.length - 1).fill(null), histUrea[histUrea.length - 1], ...forecastHigh];

  const datasets = [
    {
      label: "Urea (historical) $/mt",
      data: ureaHist,
      borderColor: "#22c55e",
      backgroundColor: "rgba(34,197,94,0.08)",
      borderWidth: 2.5,
      pointRadius: 2,
      tension: 0.3,
      fill: false,
      yAxisID: "yUrea",
    },
    {
      label: "Forecast — mean",
      data: fMean,
      borderColor: "#f59e0b",
      borderDash: [6, 4],
      borderWidth: 2.5,
      pointRadius: 0,
      tension: 0.3,
      fill: false,
      yAxisID: "yUrea",
    },
    {
      label: "Forecast — 80% range (high)",
      data: fHigh,
      borderColor: "transparent",
      backgroundColor: "rgba(245,158,11,0.15)",
      borderWidth: 0,
      pointRadius: 0,
      tension: 0.3,
      fill: "+1",
      yAxisID: "yUrea",
    },
    {
      label: "Forecast — 80% range (low)",
      data: fLow,
      borderColor: "rgba(245,158,11,0.25)",
      borderDash: [3, 3],
      borderWidth: 1,
      pointRadius: 0,
      tension: 0.3,
      fill: false,
      yAxisID: "yUrea",
    },
  ];

  if (showNatGas && natGasHist) {
    datasets.push({
      label: "Nat Gas (Henry Hub) $/MMBtu",
      data: natGasHist,
      borderColor: "#60a5fa",
      borderWidth: 2,
      pointRadius: 0,
      tension: 0.3,
      fill: false,
      yAxisID: "yGas",
    });
  }

  if (priceChart) priceChart.destroy();

  priceChart = new Chart(ctx, {
    type: "line",
    data: { labels: allLabels, datasets },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { mode: "index", intersect: false },
      plugins: {
        legend: {
          labels: { color: "#cbd5e1", font: { size: 12 } },
          onClick: (e, item, legend) => {
            // default toggle behavior
            Chart.defaults.plugins.legend.onClick.call(legend.chart, e, item, legend);
          },
        },
        tooltip: {
          callbacks: {
            label: ctx => {
              if (ctx.parsed.y === null) return null;
              const unit = ctx.dataset.yAxisID === "yGas" ? " $/MMBtu" : " $/mt";
              return `${ctx.dataset.label}: $${ctx.parsed.y.toFixed(0)}${unit}`;
            },
          },
        },
      },
      scales: {
        x: {
          ticks: { color: "#94a3b8", maxRotation: 45, autoSkip: true, maxTicksLimit: 18 },
          grid:  { color: "rgba(255,255,255,0.05)" },
        },
        yUrea: {
          type: "linear",
          position: "left",
          title: { display: true, text: "Urea $/mt", color: "#22c55e" },
          ticks: { color: "#94a3b8" },
          grid:  { color: "rgba(255,255,255,0.07)" },
        },
        yGas: {
          type: "linear",
          position: "right",
          display: !!showNatGas,
          title: { display: true, text: "Nat Gas $/MMBtu", color: "#60a5fa" },
          ticks: { color: "#60a5fa" },
          grid:  { drawOnChartArea: false },
        },
      },
    },
  });
}

function setChartLoading(loading) {
  const wrap = document.getElementById("chartWrapper");
  const spinner = document.getElementById("chartSpinner");
  if (loading) {
    wrap.classList.add("loading");
    spinner.style.display = "flex";
  } else {
    wrap.classList.remove("loading");
    spinner.style.display = "none";
  }
}

async function loadChart(showNatGas) {
  setChartLoading(true);
  try {
    const [histUrea, histGas, forecast] = await Promise.all([
      API.getPriceHistory("urea"),
      API.getNatGasHistory(),
      API.getPriceForecast("urea", 90),
    ]);

    renderPriceChart(
      histUrea.labels, histUrea.values,
      histGas.values,
      forecast.labels, forecast.mean, forecast.low, forecast.high,
      showNatGas,
    );
  } catch (err) {
    showChartError(err.message);
  } finally {
    setChartLoading(false);
  }
}

function showChartError(msg) {
  document.getElementById("chartError").textContent = "Could not load price data: " + msg;
  document.getElementById("chartError").style.display = "block";
}

// ── Buy Timing Signal ─────────────────────────────────────────────────────────

async function loadBuySignal(tonsNeeded) {
  const card = document.getElementById("signalCard");
  card.classList.add("loading");
  document.getElementById("signalContent").innerHTML = "";

  try {
    const signal = await API.getBuyTiming(tonsNeeded);
    renderBuySignal(signal);
  } catch (err) {
    document.getElementById("signalContent").innerHTML =
      `<p class="error-text">Could not load signal: ${err.message}</p>`;
  } finally {
    card.classList.remove("loading");
  }
}

function renderBuySignal(signal) {
  const urgencyClass = {
    HIGH: "urgency-high",
    MODERATE: "urgency-moderate",
    LOW: "urgency-low",
  }[signal.urgency] || "";

  const costLine = signal.tonsNeeded
    ? `<p class="signal-cost">At your usage, buying at the optimal window saves an estimated <strong>${formatCurrency(signal.savingsVsWait)}</strong> vs. waiting until peak.</p>`
    : "";

  document.getElementById("signalContent").innerHTML = `
    <div class="signal-badge ${urgencyClass}">${signal.urgency} URGENCY</div>
    <h3 class="signal-rec">${signal.recommendation}</h3>
    <p class="signal-rationale">${signal.rationale}</p>
    ${costLine}
    <div class="signal-meta">
      Current urea: <strong>$${signal.currentPrice}/mt</strong> &nbsp;|&nbsp;
      Best window: <strong>${signal.bestMonth}</strong> at ~<strong>$${signal.bestPrice}/mt</strong>
    </div>
  `;
}

// ── Exposure Calculator ───────────────────────────────────────────────────────

let savedProfile = null;   // last profile loaded from backend

function buildExposurePayload() {
  const mode = document.querySelector('input[name="inputMode"]:checked').value;

  if (mode === "direct") {
    const lbs = parseFloat(document.getElementById("fertLbs").value);
    if (!lbs || lbs <= 0) throw new Error("Enter a valid fertilizer amount.");
    return { inputMode: "direct", fertilizerLbs: lbs };
  }

  // crops mode
  const rows = document.querySelectorAll(".crop-row");
  if (!rows.length) throw new Error("Add at least one crop.");
  const crops = [];
  rows.forEach(row => {
    const type  = row.querySelector(".crop-type").value;
    const acres = parseFloat(row.querySelector(".crop-acres").value);
    if (type && acres > 0) crops.push({ type, acres });
  });
  if (!crops.length) throw new Error("Enter valid crop types and acreages.");
  return { inputMode: "crops", crops };
}

async function handleCalculate(e) {
  e.preventDefault();
  const btn = document.getElementById("calcBtn");
  btn.disabled = true;
  btn.textContent = "Calculating…";
  clearResults();

  try {
    const payload = buildExposurePayload();
    const result  = await API.calculateExposure(payload);
    renderExposureResults(result);
    // Also refresh buy signal with user's tonnage
    loadBuySignal(result.tonsUreaNeeded);
  } catch (err) {
    document.getElementById("calcError").textContent = err.message;
    document.getElementById("calcError").style.display = "block";
  } finally {
    btn.disabled = false;
    btn.textContent = "Calculate My Costs";
  }
}

async function handleSaveProfile(e) {
  e.preventDefault();
  const user = getSession();
  const btn  = document.getElementById("saveBtn");
  btn.disabled = true;
  btn.textContent = "Saving…";

  try {
    const payload = buildExposurePayload();
    await API.saveFarmerProfile(user.email, payload);
    showToast("Profile saved for " + user.email);
  } catch (err) {
    showToast("Save failed: " + err.message, "error");
  } finally {
    btn.disabled = false;
    btn.textContent = "Save Profile";
  }
}

async function loadSavedProfile(email) {
  try {
    const profile = await API.getFarmerProfile(email);
    if (!profile) return;
    savedProfile = profile;
    populateFormFromProfile(profile);
  } catch {
    // no saved profile yet — that's fine
  }
}

function populateFormFromProfile(profile) {
  if (profile.inputMode === "direct") {
    document.getElementById("modeDirectBtn").checked = true;
    toggleInputMode("direct");
    document.getElementById("fertLbs").value = profile.fertilizerLbs || "";
  } else {
    document.getElementById("modeCropsBtn").checked = true;
    toggleInputMode("crops");
    clearCropRows();
    (profile.crops || []).forEach(c => addCropRow(c.type, c.acres));
  }
  document.getElementById("profileNote").textContent =
    `Last saved: ${new Date(profile.updatedAt).toLocaleDateString()}`;
}

function renderExposureResults(result) {
  const section = document.getElementById("resultsSection");
  section.style.display = "block";

  // Tonnage summary
  document.getElementById("tonsNeeded").textContent =
    result.tonsUreaNeeded.toFixed(1) + " mt";
  document.getElementById("totalLbsN").textContent =
    result.totalLbsN ? result.totalLbsN.toLocaleString() + " lbs N" : "—";

  // Cost table
  const tbody = document.getElementById("costTableBody");
  tbody.innerHTML = "";
  (result.costByMonth || []).forEach(row => {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${row.label}</td>
      <td class="cost-cell">${formatCurrency(row.cost)}</td>
      <td class="range-cell">${formatCurrency(row.low)} – ${formatCurrency(row.high)}</td>
    `;
    tbody.appendChild(tr);
  });

  // Crop breakdown (if available)
  const breakdownEl = document.getElementById("cropBreakdown");
  if (result.breakdown && result.breakdown.length) {
    breakdownEl.style.display = "block";
    const bList = document.getElementById("breakdownList");
    bList.innerHTML = "";
    result.breakdown.forEach(b => {
      const li = document.createElement("li");
      li.innerHTML = `<span class="crop-label">${b.label}</span>
        <span class="crop-meta">${b.acres.toLocaleString()} acres · ${b.lbsN.toLocaleString()} lbs N · <em>${b.sensitivity} sensitivity</em></span>`;
      bList.appendChild(li);
    });
  } else {
    breakdownEl.style.display = "none";
  }
}

function clearResults() {
  document.getElementById("resultsSection").style.display = "none";
  document.getElementById("calcError").style.display = "none";
}

// ── Crop Row Management ───────────────────────────────────────────────────────

const CROP_OPTIONS = [
  { value: "corn",      label: "Corn" },
  { value: "wheat",     label: "Wheat" },
  { value: "cotton",    label: "Cotton" },
  { value: "sorghum",   label: "Sorghum" },
  { value: "soybeans",  label: "Soybeans" },
  { value: "hay",       label: "Hay / Alfalfa" },
  { value: "livestock", label: "Livestock Only" },
];

function buildCropSelect(selected = "") {
  return `<select class="crop-type input-field">
    <option value="">-- Select crop --</option>
    ${CROP_OPTIONS.map(o =>
      `<option value="${o.value}" ${o.value === selected ? "selected" : ""}>${o.label}</option>`
    ).join("")}
  </select>`;
}

function addCropRow(type = "", acres = "") {
  const container = document.getElementById("cropRows");
  const div = document.createElement("div");
  div.className = "crop-row";
  div.innerHTML = `
    ${buildCropSelect(type)}
    <input type="number" class="crop-acres input-field" placeholder="Acres" min="1" value="${acres}" />
    <button type="button" class="btn-icon remove-crop" title="Remove">✕</button>
  `;
  div.querySelector(".remove-crop").addEventListener("click", () => div.remove());
  container.appendChild(div);
}

function clearCropRows() {
  document.getElementById("cropRows").innerHTML = "";
}

// ── Input Mode Toggle ─────────────────────────────────────────────────────────

function toggleInputMode(mode) {
  document.getElementById("directSection").style.display = mode === "direct" ? "block" : "none";
  document.getElementById("cropsSection").style.display  = mode === "crops"  ? "block" : "none";
}

// ── Toast Notifications ───────────────────────────────────────────────────────

function showToast(msg, type = "success") {
  const toast = document.getElementById("toast");
  toast.textContent = msg;
  toast.className = "toast " + type;
  toast.style.opacity = "1";
  setTimeout(() => { toast.style.opacity = "0"; }, 3200);
}

// ── Currency Formatter (local, no API needed) ─────────────────────────────────

function formatCurrency(n) {
  if (n == null) return "—";
  return "$" + Math.round(n).toLocaleString("en-US");
}

// ── Dashboard Init ────────────────────────────────────────────────────────────

function initDashboard() {
  const user = requireAuth();
  document.getElementById("userEmail").textContent = user.email;

  // Load chart (default: no nat gas overlay)
  let showNatGas = false;
  loadChart(showNatGas);

  // Toggle nat gas overlay
  document.getElementById("toggleNatGas").addEventListener("change", e => {
    showNatGas = e.target.checked;
    loadChart(showNatGas);
  });

  // Input mode toggle
  document.querySelectorAll('input[name="inputMode"]').forEach(radio => {
    radio.addEventListener("change", e => toggleInputMode(e.target.value));
  });
  toggleInputMode("crops");   // default mode

  // Add crop row button
  document.getElementById("addCropBtn").addEventListener("click", () => addCropRow());

  // Form submission
  document.getElementById("exposureForm").addEventListener("submit", handleCalculate);
  document.getElementById("saveBtn").addEventListener("click", handleSaveProfile);

  // Buy signal button (manual trigger before form submit)
  document.getElementById("buySignalBtn").addEventListener("click", () => loadBuySignal(null));

  // Logout
  document.getElementById("logoutBtn").addEventListener("click", () => {
    sessionStorage.removeItem("agrisignal_user");
    window.location.href = "index.html";
  });

  // Load saved profile for this user
  loadSavedProfile(user.email);
}

// ── Login Page Init ───────────────────────────────────────────────────────────

function initLogin() {
  // If already logged in, redirect straight to dashboard
  if (getSession()) { window.location.href = "dashboard.html"; return; }

  document.getElementById("loginForm").addEventListener("submit", async e => {
    e.preventDefault();
    // Normalize to lowercase so User@Example.com == user@example.com
    const email = document.getElementById("emailInput").value.trim().toLowerCase();
    const errEl = document.getElementById("loginError");
    const btn   = document.getElementById("loginBtn");

    errEl.style.display = "none";

    if (!email || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
      errEl.textContent = "Enter a valid email address.";
      errEl.style.display = "block";
      return;
    }

    btn.disabled = true;
    btn.textContent = "Signing in…";

    try {
      const user = await API.login(email);
      setSession({ email: user.email });
      window.location.href = "dashboard.html";
    } catch (err) {
      errEl.textContent = err.message || "Could not reach the server. Is it running?";
      errEl.style.display = "block";
      btn.disabled = false;
      btn.textContent = "Sign In →";
    }
  });
}
