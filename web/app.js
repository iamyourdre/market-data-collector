/**
 * Antigravity Crypto Forecast Engine - Frontend Application Logic
 * Implements high-performance Canvas rendering, crosshair HUD, sub-charts,
 * dynamic model simplex visualization, and Monte Carlo barrier simulation.
 */

// Application State
const state = {
  activeData: null,
  presets: [],
  selectedPreset: "ETHUSDT_15m_1d.json",
  horizonSteps: 48,
  viewMode: "candles", // 'candles' or 'line'
  subChartType: "rsi", // 'rsi', 'macd', 'cvd', 'oi'
  visibility: {
    M6: true,
    M1: true,
    M2: true,
    M3: true,
    M4: true,
    M5: true,
    CI: true,
  },
  // Viewport zoom & pan
  viewRange: {
    startIdx: 0,
    endIdx: 0,
    totalPoints: 0,
  },
  mouse: {
    x: -1,
    y: -1,
    isHovering: false,
    isDragging: false,
    dragStartX: 0,
    dragStartRange: null,
  },
};

// Model Theme Colors
const MODEL_COLORS = {
  M6_Best_Ensemble: "#00f2fe",
  M1_Holt_Damped: "#8b5cf6",
  M2_Fourier_Harmonic: "#10b981",
  M3_Kalman_OU: "#f59e0b",
  M4_ARX_Ridge: "#ec4899",
  M5_kNN_Analog: "#06b6d4",
};

// DOM Elements
const elements = {
  presetSelect: document.getElementById("presetSelect"),
  activeSymbolText: document.getElementById("activeSymbolText"),
  metricTimeframeTag: document.getElementById("metricTimeframeTag"),
  valSpotPrice: document.getElementById("valSpotPrice"),
  val24hRange: document.getElementById("val24hRange"),
  metricBiasTag: document.getElementById("metricBiasTag"),
  valHorizonPrice: document.getElementById("valHorizonPrice"),
  valExpectedReturn: document.getElementById("valExpectedReturn"),
  valDailyVol: document.getElementById("valDailyVol"),
  valVolPersistence: document.getElementById("valVolPersistence"),
  metricPersistenceTag: document.getElementById("metricPersistenceTag"),
  valDirectionalAccuracy: document.getElementById("valDirectionalAccuracy"),
  valPathRMSE: document.getElementById("valPathRMSE"),
  metricBestModelTag: document.getElementById("metricBestModelTag"),
  chartSymbolHeader: document.getElementById("chartSymbolHeader"),
  chartCandlesCount: document.getElementById("chartCandlesCount"),
  chartIntervalBadge: document.getElementById("chartIntervalBadge"),
  forecastCanvas: document.getElementById("forecastCanvas"),
  chartViewport: document.getElementById("chartViewport"),
  chartHud: document.getElementById("chartHud"),
  hudDate: document.getElementById("hudDate"),
  hudGrid: document.getElementById("hudGrid"),
  subCanvas: document.getElementById("subCanvas"),
  modelsList: document.getElementById("modelsList"),
  metricsTableBody: document.getElementById("metricsTableBody"),
  upsideBarriersGrid: document.getElementById("upsideBarriersGrid"),
  downsideBarriersGrid: document.getElementById("downsideBarriersGrid"),
  mcPathsCount: document.getElementById("mcPathsCount"),
  inputCustomBarrier: document.getElementById("inputCustomBarrier"),
  btnSimulateCustomBarrier: document.getElementById("btnSimulateCustomBarrier"),
  customBarrierResult: document.getElementById("customBarrierResult"),
  forecastDataTableBody: document.getElementById("forecastDataTableBody"),
  btnRunForecast: document.getElementById("btnRunForecast"),
  btnModeCandles: document.getElementById("btnModeCandles"),
  btnModeLine: document.getElementById("btnModeLine"),
  btnExportCsv: document.getElementById("btnExportCsv"),
  btnExportJson: document.getElementById("btnExportJson"),
  btnOpenUpload: document.getElementById("btnOpenUpload"),
  uploadModal: document.getElementById("uploadModal"),
  btnCloseUpload: document.getElementById("btnCloseUpload"),
  btnCancelUpload: document.getElementById("btnCancelUpload"),
  btnSubmitUpload: document.getElementById("btnSubmitUpload"),
  dropzone: document.getElementById("dropzone"),
  fileInput: document.getElementById("fileInput"),
  uploadFileInfo: document.getElementById("uploadFileInfo"),
  btnOpenLiveFetch: document.getElementById("btnOpenLiveFetch"),
  liveFetchModal: document.getElementById("liveFetchModal"),
  btnCloseLiveFetch: document.getElementById("btnCloseLiveFetch"),
  btnCancelLiveFetch: document.getElementById("btnCancelLiveFetch"),
  btnDownloadJsonOnly: document.getElementById("btnDownloadJsonOnly"),
  btnSubmitLiveFetch: document.getElementById("btnSubmitLiveFetch"),
  liveSymbolInput: document.getElementById("liveSymbolInput"),
  liveTfInput: document.getElementById("liveTfInput"),
  liveDaysInput: document.getElementById("liveDaysInput"),
  liveDownloadPreview: document.getElementById("liveDownloadPreview"),
  loadingOverlay: document.getElementById("loadingOverlay"),
  loadingMessage: document.getElementById("loadingMessage"),
  toastContainer: document.getElementById("toastContainer"),
};

// ==========================================================================
// Initialization & Event Listeners
// ==========================================================================
document.addEventListener("DOMContentLoaded", async () => {
  setupEventListeners();
  setupCanvasInteractions();
  await loadPresets();
  await runForecast();
});

function setupEventListeners() {
  // Preset selector
  elements.presetSelect.addEventListener("change", (e) => {
    state.selectedPreset = e.target.value;
    runForecast();
  });

  // Horizon step buttons
  document.querySelectorAll(".horizon-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".horizon-btn").forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      state.horizonSteps = parseInt(btn.dataset.steps, 10);
      runForecast();
    });
  });

  // Run forecast button
  elements.btnRunForecast.addEventListener("click", () => {
    runForecast();
  });

  // Candlestick vs Line mode
  elements.btnModeCandles.addEventListener("click", () => {
    state.viewMode = "candles";
    elements.btnModeCandles.classList.add("active");
    elements.btnModeLine.classList.remove("active");
    renderCharts();
  });

  elements.btnModeLine.addEventListener("click", () => {
    state.viewMode = "line";
    elements.btnModeLine.classList.add("active");
    elements.btnModeCandles.classList.remove("active");
    renderCharts();
  });

  // Model Visibility Legend Toggles
  const modelCheckboxes = [
    { id: "chkM6", key: "M6" },
    { id: "chkM1", key: "M1" },
    { id: "chkM2", key: "M2" },
    { id: "chkM3", key: "M3" },
    { id: "chkM4", key: "M4" },
    { id: "chkM5", key: "M5" },
    { id: "chkCI", key: "CI" },
  ];

  modelCheckboxes.forEach(({ id, key }) => {
    const chk = document.getElementById(id);
    if (chk) {
      chk.addEventListener("change", (e) => {
        state.visibility[key] = e.target.checked;
        const parentChip = chk.closest(".toggle-chip");
        if (parentChip) {
          parentChip.classList.toggle("active", e.target.checked);
        }
        renderCharts();
      });
    }
  });

  // Subchart Tab Buttons
  document.querySelectorAll(".subchart-tab-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".subchart-tab-btn").forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      state.subChartType = btn.dataset.sub;
      renderSubChart();
    });
  });

  // Custom Barrier Simulator Button and Enter Key
  elements.btnSimulateCustomBarrier.addEventListener("click", handleCustomBarrierSimulate);
  elements.inputCustomBarrier.addEventListener("keydown", (e) => {
    if (e.key === "Enter") {
      e.preventDefault();
      handleCustomBarrierSimulate();
    }
  });

  // Export Buttons
  elements.btnExportCsv.addEventListener("click", handleExportCsv);
  elements.btnExportJson.addEventListener("click", handleExportJson);

  // Upload Modal
  elements.btnOpenUpload.addEventListener("click", () => elements.uploadModal.classList.add("open"));
  elements.btnCloseUpload.addEventListener("click", () => elements.uploadModal.classList.remove("open"));
  elements.btnCancelUpload.addEventListener("click", () => elements.uploadModal.classList.remove("open"));

  // Dropzone handling
  elements.dropzone.addEventListener("click", () => elements.fileInput.click());
  elements.fileInput.addEventListener("change", handleFileSelected);

  elements.dropzone.addEventListener("dragover", (e) => {
    e.preventDefault();
    elements.dropzone.classList.add("dragover");
  });

  elements.dropzone.addEventListener("dragleave", () => {
    elements.dropzone.classList.remove("dragover");
  });

  elements.dropzone.addEventListener("drop", (e) => {
    e.preventDefault();
    elements.dropzone.classList.remove("dragover");
    if (e.dataTransfer.files.length) {
      elements.fileInput.files = e.dataTransfer.files;
      handleFileSelected();
    }
  });

  elements.btnSubmitUpload.addEventListener("click", handleUploadSubmit);

  // Live Binance Modal & Local Download
  elements.btnOpenLiveFetch.addEventListener("click", () => {
    updateLiveDownloadPreview();
    elements.liveFetchModal.classList.add("open");
  });
  elements.btnCloseLiveFetch.addEventListener("click", () => elements.liveFetchModal.classList.remove("open"));
  elements.btnCancelLiveFetch.addEventListener("click", () => elements.liveFetchModal.classList.remove("open"));
  elements.btnDownloadJsonOnly.addEventListener("click", handleDownloadJsonOnly);
  elements.btnSubmitLiveFetch.addEventListener("click", handleLiveFetchSubmit);

  elements.liveSymbolInput.addEventListener("input", updateLiveDownloadPreview);
  elements.liveTfInput.addEventListener("change", updateLiveDownloadPreview);
  elements.liveDaysInput.addEventListener("change", updateLiveDownloadPreview);

  // Window Resize
  window.addEventListener("resize", () => {
    resizeCanvas(elements.forecastCanvas);
    resizeCanvas(elements.subCanvas);
    renderCharts();
  });
}

// ==========================================================================
// API & Data Fetching
// ==========================================================================
async function loadPresets() {
  try {
    const res = await fetch("/api/presets");
    const data = await res.json();
    state.presets = data;

    elements.presetSelect.innerHTML = "";
    data.forEach((p) => {
      const opt = document.createElement("option");
      opt.value = p.filename;
      const pPrice = p.latest_price != null ? "$" + p.latest_price.toLocaleString() : "N/A";
      opt.textContent = `${p.symbol} (${p.timeframe}, ${p.total_candles} lilin, ${pPrice})`;
      if (p.filename === state.selectedPreset) {
        opt.selected = true;
      }
      elements.presetSelect.appendChild(opt);
    });

    if (data.length && !data.some((p) => p.filename === state.selectedPreset)) {
      state.selectedPreset = data[0].filename;
    }
  } catch (err) {
    showToast(`Gagal memuat daftar preset: ${err.message}`, "error");
  }
}

async function runForecast() {
  showLoading("Menjalankan pipeline peramalan kuantitatif...");
  try {
    const url = `/api/forecast/preset/${encodeURIComponent(state.selectedPreset)}?horizon=${state.horizonSteps}&mc_sims=10000`;
    const res = await fetch(url);
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || "Gagal menghasilkan forecast");
    }
    const data = await res.json();
    state.activeData = data;

    const totalPoints = (data.historical_data?.length || 0) + (data.forecast_data?.length || 0);
    state.viewRange = {
      startIdx: 0,
      endIdx: totalPoints - 1,
      totalPoints: totalPoints,
    };

    updateDashboard();
    renderCharts();
    showToast("Peramalan selesai & model berhasil diselaraskan!", "success");
  } catch (err) {
    showToast(`Error: ${err.message}`, "error");
  } finally {
    hideLoading();
  }
}

async function handleFileSelected() {
  const file = elements.fileInput.files[0];
  if (!file) return;

  elements.uploadFileInfo.style.display = "block";
  elements.uploadFileInfo.textContent = `File terpilih: ${file.name} (${(file.size / 1024).toFixed(1)} KB)`;
  elements.btnSubmitUpload.disabled = false;
}

async function handleUploadSubmit() {
  const file = elements.fileInput.files[0];
  if (!file) return;

  elements.uploadModal.classList.remove("open");
  showLoading(`Mengunggah dan menganalisis ${file.name}...`);

  const formData = new FormData();
  formData.append("file", file);
  formData.append("horizon", state.horizonSteps);
  formData.append("mc_sims", 10000);

  try {
    const res = await fetch("/api/forecast/upload", {
      method: "POST",
      body: formData,
    });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || "Upload gagal");
    }
    const data = await res.json();
    state.activeData = data;

    const totalPoints = (data.historical_data?.length || 0) + (data.forecast_data?.length || 0);
    state.viewRange = {
      startIdx: 0,
      endIdx: totalPoints - 1,
      totalPoints: totalPoints,
    };

    updateDashboard();
    renderCharts();
    showToast(`File ${file.name} berhasil dimuat & diramalkan!`, "success");
  } catch (err) {
    showToast(`Gagal mengunggah file: ${err.message}`, "error");
  } finally {
    hideLoading();
  }
}

function getFormattedTimestamp(date = new Date()) {
  const pad = (n) => String(n).padStart(2, "0");
  const yyyy = date.getFullYear();
  const mm = pad(date.getMonth() + 1);
  const dd = pad(date.getDate());
  const hh = pad(date.getHours());
  const min = pad(date.getMinutes());
  const ss = pad(date.getSeconds());
  return `${yyyy}${mm}${dd}_${hh}${min}${ss}`;
}

function updateLiveDownloadPreview() {
  if (!elements.liveDownloadPreview) return;
  const sym = (elements.liveSymbolInput?.value || "ETHUSDT").trim().toUpperCase() || "ETHUSDT";
  const tf = elements.liveTfInput?.value || "15m";
  const days = elements.liveDaysInput?.value || "1";
  const ts = getFormattedTimestamp();
  elements.liveDownloadPreview.textContent = `${sym}_${tf}_${days}d_${ts}.json`;
}

function triggerBlobDownload(blob, filename) {
  const url = window.URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.style.display = "none";
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  setTimeout(() => {
    window.URL.revokeObjectURL(url);
    a.remove();
  }, 1000);
}

async function handleDownloadJsonOnly() {
  const symbol = elements.liveSymbolInput.value.trim().toUpperCase();
  const tf = elements.liveTfInput.value;
  const days = parseInt(elements.liveDaysInput.value, 10);

  if (!symbol) {
    showToast("Mohon masukkan simbol kripto", "error");
    return;
  }

  elements.liveFetchModal.classList.remove("open");
  showLoading(`Mengunduh dataset ${symbol} (${tf}, ${days}d) dari Binance ke local...`);

  try {
    const url = `/api/binance/download?symbol=${encodeURIComponent(symbol)}&timeframe=${tf}&days=${days}&save_server=true`;
    const res = await fetch(url);
    if (!res.ok) {
      let errDetail = "Download gagal";
      try {
        const errJson = await res.json();
        errDetail = errJson.detail || errDetail;
      } catch (_) {}
      throw new Error(errDetail);
    }

    // Ambil filename dari header atau fallback dengan timestamp
    let filename = res.headers.get("X-Dataset-Filename");
    if (!filename) {
      const cd = res.headers.get("Content-Disposition");
      if (cd && cd.includes("filename=")) {
        const match = cd.match(/filename="?([^";]+)"?/);
        if (match && match[1]) filename = match[1];
      }
    }
    if (!filename) {
      filename = `${symbol}_${tf}_${days}d_${getFormattedTimestamp()}.json`;
    }

    const blob = await res.blob();
    triggerBlobDownload(blob, filename);

    await loadPresets();
    showToast(`File ${filename} berhasil diunduh ke komputer lokal!`, "success");
  } catch (err) {
    showToast(`Gagal mengunduh file JSON: ${err.message}`, "error");
  } finally {
    hideLoading();
  }
}

async function handleLiveFetchSubmit() {
  const symbol = elements.liveSymbolInput.value.trim().toUpperCase();
  const tf = elements.liveTfInput.value;
  const days = parseInt(elements.liveDaysInput.value, 10);

  if (!symbol) {
    showToast("Mohon masukkan simbol kripto", "error");
    return;
  }

  elements.liveFetchModal.classList.remove("open");
  showLoading(`Mengambil data live Binance & meramalkan ${symbol} (${tf}, ${days}d)...`);

  try {
    const res = await fetch("/api/forecast/live", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        symbol: symbol,
        timeframe: tf,
        days: days,
        horizon_steps: state.horizonSteps,
        mc_simulations: 10000,
        save_dataset: true,
      }),
    });

    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || "Live fetch gagal");
    }

    const data = await res.json();
    state.activeData = data;

    // Otomatis download file JSON bertimestamp ke komputer lokal
    if (data.raw_dataset && data.dataset_filename) {
      const blob = new Blob([JSON.stringify(data.raw_dataset, null, 2)], {
        type: "application/json",
      });
      triggerBlobDownload(blob, data.dataset_filename);
    }

    const totalPoints = (data.historical_data?.length || 0) + (data.forecast_data?.length || 0);
    state.viewRange = {
      startIdx: 0,
      endIdx: totalPoints - 1,
      totalPoints: totalPoints,
    };

    updateDashboard();
    renderCharts();
    await loadPresets();
    showToast(`Data ${symbol} berhasil didownload (${data.dataset_filename || "JSON"}) & diramalkan!`, "success");
  } catch (err) {
    showToast(`Gagal menarik data live: ${err.message}`, "error");
  } finally {
    hideLoading();
  }
}

async function handleCustomBarrierSimulate() {
  const customPrice = parseFloat(elements.inputCustomBarrier.value);
  if (isNaN(customPrice) || customPrice <= 0) {
    showToast("Masukkan harga target yang valid", "error");
    return;
  }

  if (!state.activeData) return;

  const lastClose = state.activeData.summary.last_close;
  const ensPath = state.activeData.forecast_data.map((r) => r.M6_Best_Ensemble);
  const ci80Up = state.activeData.forecast_data.map((r) => r.ci_80_upper);

  const isUpside = customPrice >= lastClose;
  const upsideList = isUpside ? [customPrice] : [];
  const downsideList = !isUpside ? [customPrice] : [];

  try {
    elements.btnSimulateCustomBarrier.textContent = "Menghitung...";
    elements.btnSimulateCustomBarrier.disabled = true;

    const res = await fetch("/api/barriers/simulate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        current_price: lastClose,
        ensemble_path: ensPath,
        ci_80_upper: ci80Up,
        upside_barriers: upsideList,
        downside_barriers: downsideList,
        step_minutes: state.activeData.metadata.step_minutes || 15,
        mc_simulations: 10000,
        student_df: 6,
      }),
    });

    const pool = isUpside ? data.upside : data.downside;
    const resultObj = pool[String(customPrice)] || pool[customPrice.toFixed(1)] || pool[customPrice.toFixed(2)] || (pool ? Object.values(pool)[0] : null);

    if (resultObj) {
      const distSign = resultObj.distance_pct > 0 ? "+" : "";
      elements.customBarrierResult.style.display = "block";
      elements.customBarrierResult.innerHTML = `
        🎯 Target $${customPrice.toLocaleString()} (${distSign}${resultObj.distance_pct}%):<br>
        • Peluang Sentuh 24h: <b>${resultObj.touch_24h_pct}%</b><br>
        • Peluang Sentuh Horizon (${state.activeData.summary.horizon_hours}h): <b>${resultObj.touch_horizon_pct}%</b>
      `;
    }
  } catch (err) {
    showToast(`Simulasi barrier gagal: ${err.message}`, "error");
  } finally {
    elements.btnSimulateCustomBarrier.textContent = "Hitung Peluang";
    elements.btnSimulateCustomBarrier.disabled = false;
  }
}

// ==========================================================================
// Dashboard Update Logic
// ==========================================================================
function updateDashboard() {
  if (!state.activeData) return;

  const data = state.activeData;
  const meta = data.metadata || {};
  const sum = data.summary || {};
  const garch = data.garch_params || {};
  const metrics = data.backtest_metrics || {};

  // Header badges
  const symbol = meta.symbol || "ETHUSDT";
  const tf = meta.timeframe || `${meta.step_minutes}m`;
  elements.activeSymbolText.textContent = `${symbol} • ${tf}`;
  elements.chartSymbolHeader.textContent = symbol;
  elements.chartCandlesCount.textContent = `${data.historical_data?.length || 0} Lilin`;
  elements.chartIntervalBadge.textContent = `${meta.step_minutes || 15} Menit`;
  elements.metricTimeframeTag.textContent = tf;

  // 1. Spot Price
  const lastClose = sum.last_close || 0;
  elements.valSpotPrice.textContent = `$${formatPrice(lastClose)}`;

  // Historical 24h range
  const hist = data.historical_data || [];
  if (hist.length) {
    const recentCandles = hist.slice(-Math.min(hist.length, 96));
    const highs = recentCandles.map((c) => c.high);
    const lows = recentCandles.map((c) => c.low);
    const minP = Math.min(...lows);
    const maxP = Math.max(...highs);
    const minStr = "$" + formatPrice(minP);
    const maxStr = "$" + formatPrice(maxP);
    elements.val24hRange.textContent = `${minStr} - ${maxStr}`;
  }

  // 2. Ensemble Horizon Target
  const target = sum.horizon_target || 0;
  const retPct = sum.expected_return_pct || 0;
  elements.valHorizonPrice.textContent = `$${formatPrice(target)}`;

  const retEl = elements.valExpectedReturn;
  const sign = retPct >= 0 ? "+" : "";
  retEl.textContent = `${sign}${retPct.toFixed(2)}%`;
  retEl.className = `metric-change ${retPct >= 0 ? "up" : "down"}`;

  const biasTag = elements.metricBiasTag;
  const biasStr = sum.direction || "NEUTRAL";
  biasTag.textContent = biasStr;
  biasTag.className = `metric-tag tag-${biasStr.toLowerCase()}`;

  // 3. GARCH Volatility
  const dailyVol = garch.daily_vol_pct || 0;
  const persistence = garch.persistence || 0;
  elements.valDailyVol.textContent = `${dailyVol.toFixed(2)}%`;
  elements.metricPersistenceTag.textContent = `P: ${persistence.toFixed(2)}`;

  let volRegime = "Moderat";
  if (dailyVol > 4.5) volRegime = "Sangat Tinggi (Fat-Tailed)";
  else if (dailyVol > 2.5) volRegime = "Tinggi";
  else if (dailyVol < 1.0) volRegime = "Rendah / Konsolidasi";
  elements.valVolPersistence.textContent = volRegime;

  // 4. Directional Accuracy & Best Model
  const bestEns = metrics.M6_Best_Ensemble || {};
  elements.valDirectionalAccuracy.textContent = `${(bestEns.DA_Avg || 0).toFixed(1)}%`;
  elements.valPathRMSE.textContent = `$${formatPrice(bestEns.RMSE_Path || 0)}`;

  // Find model with highest weight
  const weights = data.ensemble_weights || {};
  let bestName = "M2 Fourier";
  let maxW = 0;
  for (const [m, w] of Object.entries(weights)) {
    if (w > maxW) {
      maxW = w;
      bestName = formatModelName(m);
    }
  }
  elements.metricBestModelTag.textContent = `Top: ${bestName}`;

  // Update panels
  updateModelsList();
  updateMetricsTable();
  updateBarriersPanel();
  updateDataTable();
}

function updateModelsList() {
  const data = state.activeData;
  if (!data) return;

  const weights = data.ensemble_weights || {};
  const metrics = data.backtest_metrics || {};

  elements.modelsList.innerHTML = "";

  const modelDescriptions = {
    M1_Holt_Damped: "Holt-Winters Damped Trend Smoothing",
    M2_Fourier_Harmonic: "Spectral Harmonic FFT + Damped Drift",
    M3_Kalman_OU: "Dual-State Kalman Filter + OU Equilibrium",
    M4_ARX_Ridge: "Direct Multi-Horizon ARX Ridge Exogenous",
    M5_kNN_Analog: "Non-Parametric Trajectory Analog Pattern",
  };

  for (const [mName, weight] of Object.entries(weights)) {
    const color = MODEL_COLORS[mName] || "#38bdf8";
    const mMetric = metrics[mName] || {};
    const weightPct = (weight * 100).toFixed(1);
    const rmseText = "$" + formatPrice(mMetric.RMSE_Path || 0);
    const mapeText = (mMetric.MAPE_Path || 0).toFixed(2) + "%";
    const da4Text = (mMetric.DA_4h || 0).toFixed(1) + "%";
    const daAvgText = (mMetric.DA_Avg || 0).toFixed(1) + "%";
    const desc = modelDescriptions[mName] || "";

    const row = document.createElement("div");
    row.className = "model-row";
    row.innerHTML = `
      <div class="model-row-head">
        <div class="model-name">
          <span style="display:inline-block; width:10px; height:10px; border-radius:50%; background:${color};"></span>
          <span>${formatModelName(mName)}</span>
          <span style="font-size:0.7rem; color:var(--text-muted); font-weight:normal;">(${desc})</span>
        </div>
        <div class="model-weight-badge" style="color: ${color};">${weightPct}%</div>
      </div>
      <div class="progress-track">
        <div class="progress-fill" style="width: ${weightPct}%; background: ${color};"></div>
      </div>
      <div class="model-metrics-row">
        <span>Path RMSE: <b>${rmseText}</b></span>
        <span>Path MAPE: <b>${mapeText}</b></span>
        <span>4h DA: <b>${da4Text}</b></span>
        <span>Avg DA: <b>${daAvgText}</b></span>
      </div>
    `;
    elements.modelsList.appendChild(row);
  }
}

function updateMetricsTable() {
  const data = state.activeData;
  if (!data) return;

  const metrics = data.backtest_metrics || {};
  const weights = data.ensemble_weights || {};

  elements.metricsTableBody.innerHTML = "";

  for (const [mName, m] of Object.entries(metrics)) {
    const isEnsemble = mName === "M6_Best_Ensemble";
    const wText = isEnsemble ? "100.0%" : ((weights[mName] || 0) * 100).toFixed(1) + "%";
    const color = MODEL_COLORS[mName] || "#00f2fe";
    const daColor = (m.DA_Avg || 0) >= 60 ? "var(--color-green)" : "var(--text-main)";

    const tr = document.createElement("tr");
    if (isEnsemble) {
      tr.style.background = "rgba(0, 242, 254, 0.08)";
      tr.style.fontWeight = "bold";
    }

    const rmseStr = "$" + formatPrice(m.RMSE_Path || 0);
    const maeStr = "$" + formatPrice(m.MAE_Path || 0);
    const mapeStr = (m.MAPE_Path || 0).toFixed(2) + "%";
    const da4Str = (m.DA_4h || 0).toFixed(1) + "%";
    const daAvgStr = (m.DA_Avg || 0).toFixed(1) + "%";

    tr.innerHTML = `
      <td style="color: ${color}">${formatModelName(mName)}</td>
      <td>${wText}</td>
      <td>${rmseStr}</td>
      <td>${maeStr}</td>
      <td>${mapeStr}</td>
      <td>${da4Str}</td>
      <td style="color: ${daColor}">${daAvgStr}</td>
    `;
    elements.metricsTableBody.appendChild(tr);
  }
}

function updateBarriersPanel() {
  const data = state.activeData;
  if (!data || !data.barrier_probabilities) return;

  const barriers = data.barrier_probabilities;
  const upside = barriers.upside || {};
  const downside = barriers.downside || {};

  elements.upsideBarriersGrid.innerHTML = "";
  for (const [priceStr, info] of Object.entries(upside)) {
    const card = document.createElement("div");
    card.className = "barrier-card upside";
    const prob24 = info.touch_24h_pct || 0;
    const color = prob24 > 70 ? "var(--color-green)" : prob24 > 40 ? "var(--color-cyan)" : "var(--text-muted)";
    const priceFormatted = "$" + formatPrice(parseFloat(priceStr));

    card.innerHTML = `
      <div class="barrier-price">${priceFormatted}</div>
      <div class="barrier-dist" style="color:var(--color-green);">+${info.distance_pct}%</div>
      <div class="barrier-prob-ring" style="color: ${color};">${prob24}%</div>
      <div class="prob-24h-label">Peluang 24h</div>
    `;
    elements.upsideBarriersGrid.appendChild(card);
  }

  elements.downsideBarriersGrid.innerHTML = "";
  for (const [priceStr, info] of Object.entries(downside)) {
    const card = document.createElement("div");
    card.className = "barrier-card downside";
    const prob24 = info.touch_24h_pct || 0;
    const color = prob24 > 70 ? "var(--color-red)" : prob24 > 40 ? "var(--color-amber)" : "var(--text-muted)";
    const priceFormatted = "$" + formatPrice(parseFloat(priceStr));

    card.innerHTML = `
      <div class="barrier-price">${priceFormatted}</div>
      <div class="barrier-dist" style="color:var(--color-red);">${info.distance_pct}%</div>
      <div class="barrier-prob-ring" style="color: ${color};">${prob24}%</div>
      <div class="prob-24h-label">Peluang 24h</div>
    `;
    elements.downsideBarriersGrid.appendChild(card);
  }
}

function updateDataTable() {
  const data = state.activeData;
  if (!data || !data.forecast_data) return;

  const rows = data.forecast_data;
  elements.forecastDataTableBody.innerHTML = "";

  rows.slice(0, 48).forEach((r) => {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${formatDateTime(r.datetime)}</td>
      <td style="color:var(--color-cyan); font-weight:bold;">$${formatPrice(r.M6_Best_Ensemble)}</td>
      <td>$${formatPrice(r.ci_50_lower)}</td>
      <td>$${formatPrice(r.ci_50_upper)}</td>
      <td>$${formatPrice(r.ci_80_lower)}</td>
      <td>$${formatPrice(r.ci_80_upper)}</td>
      <td>$${formatPrice(r.ci_95_lower)}</td>
      <td>$${formatPrice(r.ci_95_upper)}</td>
    `;
    elements.forecastDataTableBody.appendChild(tr);
  });
}

// ==========================================================================
// Custom Interactive Canvas Chart Engine
// ==========================================================================
function setupCanvasInteractions() {
  const canvas = elements.forecastCanvas;
  const viewport = elements.chartViewport;

  viewport.addEventListener("mousemove", (e) => {
    const rect = canvas.getBoundingClientRect();
    state.mouse.x = e.clientX - rect.left;
    state.mouse.y = e.clientY - rect.top;
    state.mouse.isHovering = true;

    if (state.mouse.isDragging) {
      const dx = state.mouse.x - state.mouse.dragStartX;
      const count = state.viewRange.totalPoints;
      const rangeSpan = state.mouse.dragStartRange.endIdx - state.mouse.dragStartRange.startIdx;
      const pxPerPoint = canvas.width / (window.devicePixelRatio * rangeSpan);
      const shiftPoints = Math.round(dx / pxPerPoint);

      let newStart = state.mouse.dragStartRange.startIdx - shiftPoints;
      let newEnd = state.mouse.dragStartRange.endIdx - shiftPoints;

      if (newStart < 0) {
        newEnd -= newStart;
        newStart = 0;
      }
      if (newEnd >= count) {
        const diff = newEnd - count + 1;
        newStart = Math.max(0, newStart - diff);
        newEnd = count - 1;
      }

      state.viewRange.startIdx = newStart;
      state.viewRange.endIdx = newEnd;
    }

    renderCharts();
  });

  viewport.addEventListener("mouseleave", () => {
    state.mouse.isHovering = false;
    state.mouse.isDragging = false;
    elements.chartHud.style.display = "none";
    renderCharts();
  });

  viewport.addEventListener("mousedown", (e) => {
    state.mouse.isDragging = true;
    state.mouse.dragStartX = state.mouse.x;
    state.mouse.dragStartRange = { ...state.viewRange };
  });

  window.addEventListener("mouseup", () => {
    state.mouse.isDragging = false;
  });

  viewport.addEventListener("wheel", (e) => {
    e.preventDefault();
    const count = state.viewRange.totalPoints;
    if (count <= 10) return;

    const zoomFactor = e.deltaY > 0 ? 1.15 : 0.85;
    const currentSpan = state.viewRange.endIdx - state.viewRange.startIdx;
    const newSpan = Math.max(10, Math.min(count, Math.round(currentSpan * zoomFactor)));

    const mouseRatio = state.mouse.x / (canvas.width / window.devicePixelRatio);
    const centerIdx = state.viewRange.startIdx + Math.round(currentSpan * mouseRatio);

    let newStart = Math.max(0, centerIdx - Math.round(newSpan * mouseRatio));
    let newEnd = Math.min(count - 1, newStart + newSpan);

    if (newEnd - newStart < newSpan && newStart > 0) {
      newStart = Math.max(0, newEnd - newSpan);
    }

    state.viewRange.startIdx = newStart;
    state.viewRange.endIdx = newEnd;
    renderCharts();
  });

  viewport.addEventListener("dblclick", () => {
    state.viewRange.startIdx = 0;
    state.viewRange.endIdx = state.viewRange.totalPoints - 1;
    renderCharts();
  });
}

function resizeCanvas(canvas) {
  if (!canvas) return;
  const dpr = window.devicePixelRatio || 1;
  const rect = canvas.getBoundingClientRect();
  canvas.width = rect.width * dpr;
  canvas.height = rect.height * dpr;
}

function renderCharts() {
  renderMainChart();
  renderSubChart();
}

function renderMainChart() {
  const canvas = elements.forecastCanvas;
  if (!canvas || !state.activeData) return;

  const ctx = canvas.getContext("2d");
  const dpr = window.devicePixelRatio || 1;
  const W = canvas.width / dpr;
  const H = canvas.height / dpr;

  ctx.save();
  ctx.scale(dpr, dpr);
  ctx.clearRect(0, 0, W, H);

  const hist = state.activeData.historical_data || [];
  const fc = state.activeData.forecast_data || [];
  const nHist = hist.length;
  const nFc = fc.length;
  const totalPoints = nHist + nFc;

  if (totalPoints === 0) {
    ctx.restore();
    return;
  }

  let startIdx = Math.max(0, state.viewRange.startIdx);
  let endIdx = Math.min(totalPoints - 1, state.viewRange.endIdx);
  if (endIdx <= startIdx) endIdx = startIdx + 1;
  const visiblePoints = endIdx - startIdx + 1;

  const padTop = 25;
  const padBottom = 35;
  const padLeft = 15;
  const padRight = 75;
  const plotW = W - padLeft - padRight;
  const plotH = H - padTop - padBottom;

  let minP = Infinity;
  let maxP = -Infinity;

  for (let i = startIdx; i <= endIdx; i++) {
    if (i < nHist) {
      const c = hist[i];
      if (c.low < minP) minP = c.low;
      if (c.high > maxP) maxP = c.high;
    } else {
      const idxFc = i - nHist;
      const f = fc[idxFc];
      if (f) {
        if (state.visibility.CI) {
          if (f.ci_95_lower < minP) minP = f.ci_95_lower;
          if (f.ci_95_upper > maxP) maxP = f.ci_95_upper;
        } else {
          if (f.M6_Best_Ensemble < minP) minP = f.M6_Best_Ensemble;
          if (f.M6_Best_Ensemble > maxP) maxP = f.M6_Best_Ensemble;
        }
      }
    }
  }

  if (minP === Infinity) minP = 100;
  if (maxP === -Infinity) maxP = 200;
  const pMargin = (maxP - minP) * 0.08 || 1.0;
  minP -= pMargin;
  maxP += pMargin;

  const getX = (idx) => padLeft + ((idx - startIdx) / (visiblePoints - 1)) * plotW;
  const getY = (price) => padTop + (1.0 - (price - minP) / (maxP - minP)) * plotH;

  // 1. Forecast Zone Background
  if (nHist <= endIdx) {
    const splitX = Math.max(padLeft, getX(nHist - 1));
    const rightX = Math.min(W - padRight, getX(endIdx));

    ctx.fillStyle = "rgba(0, 242, 254, 0.025)";
    ctx.fillRect(splitX, padTop, rightX - splitX, plotH);

    ctx.beginPath();
    ctx.setLineDash([4, 4]);
    ctx.strokeStyle = "rgba(0, 242, 254, 0.4)";
    ctx.lineWidth = 1.5;
    ctx.moveTo(splitX, padTop);
    ctx.lineTo(splitX, padTop + plotH);
    ctx.stroke();
    ctx.setLineDash([]);

    ctx.fillStyle = "var(--color-cyan)";
    ctx.font = "bold 9px var(--font-mono)";
    ctx.textAlign = "center";
    ctx.fillText("PROYEKSI MASA DEPAN →", splitX + (rightX - splitX) / 2, padTop + 14);
  }

  // 2. Horizontal Grid & Price Ticks
  const nTicks = 6;
  ctx.textAlign = "left";
  ctx.font = "10px var(--font-mono)";
  ctx.strokeStyle = "rgba(255, 255, 255, 0.05)";
  ctx.lineWidth = 1;

  for (let i = 0; i <= nTicks; i++) {
    const tickPrice = minP + (i / nTicks) * (maxP - minP);
    const tickY = getY(tickPrice);

    ctx.beginPath();
    ctx.moveTo(padLeft, tickY);
    ctx.lineTo(W - padRight, tickY);
    ctx.stroke();

    ctx.fillStyle = "var(--text-muted)";
    ctx.fillText("$" + formatPrice(tickPrice), W - padRight + 8, tickY + 3);
  }

  // 3. GARCH Confidence Cones
  if (state.visibility.CI && nFc > 0) {
    let firstX = getX(nHist - 1);
    let firstY = getY(hist[nHist - 1].close);

    // 95% Cone
    ctx.beginPath();
    ctx.moveTo(firstX, firstY);
    for (let j = 0; j < nFc; j++) {
      const idx = nHist + j;
      if (idx >= startIdx && idx <= endIdx) {
        ctx.lineTo(getX(idx), getY(fc[j].ci_95_upper));
      }
    }
    for (let j = nFc - 1; j >= 0; j--) {
      const idx = nHist + j;
      if (idx >= startIdx && idx <= endIdx) {
        ctx.lineTo(getX(idx), getY(fc[j].ci_95_lower));
      }
    }
    ctx.closePath();
    ctx.fillStyle = "rgba(0, 242, 254, 0.05)";
    ctx.fill();

    // 80% Cone
    ctx.beginPath();
    ctx.moveTo(firstX, firstY);
    for (let j = 0; j < nFc; j++) {
      const idx = nHist + j;
      if (idx >= startIdx && idx <= endIdx) {
        ctx.lineTo(getX(idx), getY(fc[j].ci_80_upper));
      }
    }
    for (let j = nFc - 1; j >= 0; j--) {
      const idx = nHist + j;
      if (idx >= startIdx && idx <= endIdx) {
        ctx.lineTo(getX(idx), getY(fc[j].ci_80_lower));
      }
    }
    ctx.closePath();
    ctx.fillStyle = "rgba(0, 242, 254, 0.09)";
    ctx.fill();

    // 50% Cone
    ctx.beginPath();
    ctx.moveTo(firstX, firstY);
    for (let j = 0; j < nFc; j++) {
      const idx = nHist + j;
      if (idx >= startIdx && idx <= endIdx) {
        ctx.lineTo(getX(idx), getY(fc[j].ci_50_upper));
      }
    }
    for (let j = nFc - 1; j >= 0; j--) {
      const idx = nHist + j;
      if (idx >= startIdx && idx <= endIdx) {
        ctx.lineTo(getX(idx), getY(fc[j].ci_50_lower));
      }
    }
    ctx.closePath();
    ctx.fillStyle = "rgba(0, 242, 254, 0.16)";
    ctx.fill();
  }

  // 4. Historical Candlesticks / Line
  const barW = Math.max(1, (plotW / visiblePoints) * 0.7);

  if (state.viewMode === "candles") {
    for (let i = startIdx; i <= Math.min(nHist - 1, endIdx); i++) {
      const c = hist[i];
      const x = getX(i);
      const isBull = c.close >= c.open;
      const color = isBull ? "#10b981" : "#f43f5e";

      ctx.strokeStyle = color;
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.moveTo(x, getY(c.high));
      ctx.lineTo(x, getY(c.low));
      ctx.stroke();

      const yOpen = getY(c.open);
      const yClose = getY(c.close);
      const bodyTop = Math.min(yOpen, yClose);
      const bodyH = Math.max(2, Math.abs(yClose - yOpen));

      ctx.fillStyle = color;
      ctx.fillRect(x - barW / 2, bodyTop, barW, bodyH);
    }
  } else {
    ctx.beginPath();
    let started = false;
    for (let i = startIdx; i <= Math.min(nHist - 1, endIdx); i++) {
      const x = getX(i);
      const y = getY(hist[i].close);
      if (!started) {
        ctx.moveTo(x, y);
        started = true;
      } else {
        ctx.lineTo(x, y);
      }
    }
    ctx.strokeStyle = "#ffffff";
    ctx.lineWidth = 1.8;
    ctx.stroke();
  }

  // 5. Individual Base Model Paths
  const baseModels = [
    { key: "M1", colKey: "M1_Holt_Damped", color: MODEL_COLORS.M1_Holt_Damped },
    { key: "M2", colKey: "M2_Fourier_Harmonic", color: MODEL_COLORS.M2_Fourier_Harmonic },
    { key: "M3", colKey: "M3_Kalman_OU", color: MODEL_COLORS.M3_Kalman_OU },
    { key: "M4", colKey: "M4_ARX_Ridge", color: MODEL_COLORS.M4_ARX_Ridge },
    { key: "M5", colKey: "M5_kNN_Analog", color: MODEL_COLORS.M5_kNN_Analog },
  ];

  baseModels.forEach(({ key, colKey, color }) => {
    if (!state.visibility[key] || nFc === 0) return;

    ctx.beginPath();
    ctx.strokeStyle = color;
    ctx.lineWidth = 1.2;
    ctx.setLineDash([3, 2]);

    const startX = getX(nHist - 1);
    const startY = getY(hist[nHist - 1].close);
    ctx.moveTo(startX, startY);

    for (let j = 0; j < nFc; j++) {
      const idx = nHist + j;
      if (idx >= startIdx && idx <= endIdx) {
        ctx.lineTo(getX(idx), getY(fc[j][colKey]));
      }
    }
    ctx.stroke();
    ctx.setLineDash([]);
  });

  // 6. M6 Best Ensemble Forecast Path
  if (state.visibility.M6 && nFc > 0) {
    ctx.beginPath();
    ctx.strokeStyle = "var(--color-cyan)";
    ctx.lineWidth = 2.8;

    ctx.shadowColor = "rgba(0, 242, 254, 0.6)";
    ctx.shadowBlur = 10;

    const startX = getX(nHist - 1);
    const startY = getY(hist[nHist - 1].close);
    ctx.moveTo(startX, startY);

    for (let j = 0; j < nFc; j++) {
      const idx = nHist + j;
      if (idx >= startIdx && idx <= endIdx) {
        ctx.lineTo(getX(idx), getY(fc[j].M6_Best_Ensemble));
      }
    }
    ctx.stroke();
    ctx.shadowBlur = 0;
  }

  // 7. Crosshair & Tooltip HUD
  if (state.mouse.isHovering && state.mouse.x >= padLeft && state.mouse.x <= W - padRight) {
    const mouseRatio = (state.mouse.x - padLeft) / plotW;
    const hoverIdx = Math.round(startIdx + mouseRatio * (visiblePoints - 1));

    if (hoverIdx >= 0 && hoverIdx < totalPoints) {
      const crossX = getX(hoverIdx);
      const crossY = state.mouse.y;

      ctx.beginPath();
      ctx.setLineDash([3, 3]);
      ctx.strokeStyle = "rgba(255, 255, 255, 0.3)";
      ctx.lineWidth = 1;

      ctx.moveTo(crossX, padTop);
      ctx.lineTo(crossX, padTop + plotH);

      ctx.moveTo(padLeft, crossY);
      ctx.lineTo(W - padRight, crossY);
      ctx.stroke();
      ctx.setLineDash([]);

      const hoverPrice = maxP - ((crossY - padTop) / plotH) * (maxP - minP);
      ctx.fillStyle = "var(--color-cyan)";
      ctx.fillRect(W - padRight + 2, crossY - 9, padRight - 5, 18);
      ctx.fillStyle = "#050811";
      ctx.font = "bold 9px var(--font-mono)";
      ctx.fillText("$" + formatPrice(hoverPrice), W - padRight + 6, crossY + 3);

      updateHudTooltip(hoverIdx, crossX, crossY);
    }
  }

  ctx.restore();
}

function updateHudTooltip(idx, screenX, screenY) {
  const data = state.activeData;
  const hist = data.historical_data || [];
  const fc = data.forecast_data || [];
  const nHist = hist.length;

  elements.chartHud.style.display = "block";

  if (idx < nHist) {
    const c = hist[idx];
    elements.hudDate.textContent = "[HISTORIS] " + formatDateTime(c.datetime);
    elements.hudGrid.innerHTML = `
      <span>Open:</span><span class="hud-val">$${formatPrice(c.open)}</span>
      <span>High:</span><span class="hud-val">$${formatPrice(c.high)}</span>
      <span>Low:</span><span class="hud-val">$${formatPrice(c.low)}</span>
      <span>Close:</span><span class="hud-val" style="color:var(--color-cyan);">$${formatPrice(c.close)}</span>
      <span>Volume:</span><span class="hud-val">${c.volume?.toLocaleString()}</span>
      <span>RSI (14):</span><span class="hud-val">${c.rsi_14?.toFixed(1) || "--"}</span>
    `;
  } else {
    const j = idx - nHist;
    const f = fc[j];
    if (!f) return;

    elements.hudDate.textContent = `[PROYEKSI +${j + 1}] ${formatDateTime(f.datetime)}`;
    elements.hudGrid.innerHTML = `
      <span>M6 Ensemble:</span><span class="hud-val" style="color:var(--color-cyan); font-weight:bold;">$${formatPrice(f.M6_Best_Ensemble)}</span>
      <span>CI 80% (Bawah/Atas):</span><span class="hud-val">$${formatPrice(f.ci_80_lower)} / $${formatPrice(f.ci_80_upper)}</span>
      <span>M1 Holt-Winters:</span><span class="hud-val" style="color:#8b5cf6;">$${formatPrice(f.M1_Holt_Damped)}</span>
      <span>M2 Fourier FFT:</span><span class="hud-val" style="color:#10b981;">$${formatPrice(f.M2_Fourier_Harmonic)}</span>
      <span>M3 Kalman OU:</span><span class="hud-val" style="color:#f59e0b;">$${formatPrice(f.M3_Kalman_OU)}</span>
      <span>M4 ARX-Ridge:</span><span class="hud-val" style="color:#ec4899;">$${formatPrice(f.M4_ARX_Ridge)}</span>
      <span>M5 k-NN Analog:</span><span class="hud-val" style="color:#06b6d4;">$${formatPrice(f.M5_kNN_Analog)}</span>
    `;
  }

  const hudW = elements.chartHud.offsetWidth || 260;
  let posX = screenX + 15;
  if (posX + hudW > elements.forecastCanvas.width / (window.devicePixelRatio || 1) - 60) {
    posX = screenX - hudW - 15;
  }
  elements.chartHud.style.left = `${Math.max(10, posX)}px`;
  elements.chartHud.style.top = `15px`;
}

// ==========================================================================
// Sub-Chart Engine (RSI / MACD / CVD / OI)
// ==========================================================================
function renderSubChart() {
  const canvas = elements.subCanvas;
  if (!canvas || !state.activeData) return;

  const ctx = canvas.getContext("2d");
  const dpr = window.devicePixelRatio || 1;
  const W = canvas.width / dpr;
  const H = canvas.height / dpr;

  ctx.save();
  ctx.scale(dpr, dpr);
  ctx.clearRect(0, 0, W, H);

  const hist = state.activeData.historical_data || [];
  const nHist = hist.length;
  const totalPoints = state.viewRange.totalPoints;

  const padLeft = 15;
  const padRight = 75;
  const padTop = 15;
  const padBottom = 20;
  const plotW = W - padLeft - padRight;
  const plotH = H - padTop - padBottom;

  const startIdx = Math.max(0, state.viewRange.startIdx);
  const endIdx = Math.min(totalPoints - 1, state.viewRange.endIdx);
  const visiblePoints = Math.max(2, endIdx - startIdx + 1);

  const getX = (idx) => padLeft + ((idx - startIdx) / (visiblePoints - 1)) * plotW;

  if (state.subChartType === "rsi") {
    const y70 = padTop + (1.0 - 70 / 100) * plotH;
    const y30 = padTop + (1.0 - 30 / 100) * plotH;
    const y50 = padTop + (1.0 - 50 / 100) * plotH;

    ctx.strokeStyle = "rgba(244, 63, 94, 0.4)";
    ctx.setLineDash([3, 3]);
    ctx.beginPath();
    ctx.moveTo(padLeft, y70);
    ctx.lineTo(W - padRight, y70);
    ctx.stroke();

    ctx.strokeStyle = "rgba(16, 185, 129, 0.4)";
    ctx.beginPath();
    ctx.moveTo(padLeft, y30);
    ctx.lineTo(W - padRight, y30);
    ctx.stroke();

    ctx.strokeStyle = "rgba(255, 255, 255, 0.1)";
    ctx.beginPath();
    ctx.moveTo(padLeft, y50);
    ctx.lineTo(W - padRight, y50);
    ctx.stroke();
    ctx.setLineDash([]);

    ctx.beginPath();
    ctx.strokeStyle = "var(--color-purple)";
    ctx.lineWidth = 1.6;
    let started = false;

    for (let i = startIdx; i <= Math.min(nHist - 1, endIdx); i++) {
      const val = hist[i].rsi_14 || 50;
      const x = getX(i);
      const y = padTop + (1.0 - val / 100) * plotH;
      if (!started) {
        ctx.moveTo(x, y);
        started = true;
      } else {
        ctx.lineTo(x, y);
      }
    }
    ctx.stroke();

    ctx.fillStyle = "var(--text-muted)";
    ctx.font = "9px var(--font-mono)";
    ctx.fillText("70 OB", W - padRight + 8, y70 + 3);
    ctx.fillText("30 OS", W - padRight + 8, y30 + 3);

  } else if (state.subChartType === "macd") {
    let maxAbs = 0.01;
    for (let i = startIdx; i <= Math.min(nHist - 1, endIdx); i++) {
      const hVal = Math.abs(hist[i].macd_hist || 0);
      if (hVal > maxAbs) maxAbs = hVal;
    }

    const yZero = padTop + plotH / 2;
    ctx.strokeStyle = "rgba(255, 255, 255, 0.1)";
    ctx.beginPath();
    ctx.moveTo(padLeft, yZero);
    ctx.lineTo(W - padRight, yZero);
    ctx.stroke();

    const barW = Math.max(1, (plotW / visiblePoints) * 0.6);
    for (let i = startIdx; i <= Math.min(nHist - 1, endIdx); i++) {
      const val = hist[i].macd_hist || 0;
      const x = getX(i);
      const barH = (val / maxAbs) * (plotH / 2);
      ctx.fillStyle = val >= 0 ? "rgba(16, 185, 129, 0.7)" : "rgba(244, 63, 94, 0.7)";
      ctx.fillRect(x - barW / 2, yZero, barW, -barH);
    }

  } else if (state.subChartType === "cvd") {
    let minCvd = Infinity;
    let maxCvd = -Infinity;
    for (let i = startIdx; i <= Math.min(nHist - 1, endIdx); i++) {
      const val = hist[i].cvd_16 || 0;
      if (val < minCvd) minCvd = val;
      if (val > maxCvd) maxCvd = val;
    }
    if (minCvd === Infinity) minCvd = -1;
    if (maxCvd === -Infinity) maxCvd = 1;

    ctx.beginPath();
    ctx.strokeStyle = "var(--color-cyan)";
    ctx.lineWidth = 1.6;
    let started = false;

    for (let i = startIdx; i <= Math.min(nHist - 1, endIdx); i++) {
      const val = hist[i].cvd_16 || 0;
      const x = getX(i);
      const y = padTop + (1.0 - (val - minCvd) / (maxCvd - minCvd + 1e-8)) * plotH;
      if (!started) {
        ctx.moveTo(x, y);
        started = true;
      } else {
        ctx.lineTo(x, y);
      }
    }
    ctx.stroke();

  } else if (state.subChartType === "oi") {
    let minOi = Infinity;
    let maxOi = -Infinity;
    for (let i = startIdx; i <= Math.min(nHist - 1, endIdx); i++) {
      const val = hist[i].open_interest || 0;
      if (val < minOi) minOi = val;
      if (val > maxOi) maxOi = val;
    }
    if (minOi === Infinity) minOi = 0;
    if (maxOi === -Infinity) maxOi = 1000;

    ctx.beginPath();
    ctx.strokeStyle = "var(--color-amber)";
    ctx.lineWidth = 1.6;
    let started = false;

    for (let i = startIdx; i <= Math.min(nHist - 1, endIdx); i++) {
      const val = hist[i].open_interest || 0;
      const x = getX(i);
      const y = padTop + (1.0 - (val - minOi) / (maxOi - minOi + 1e-8)) * plotH;
      if (!started) {
        ctx.moveTo(x, y);
        started = true;
      } else {
        ctx.lineTo(x, y);
      }
    }
    ctx.stroke();
  }

  ctx.restore();
}

// ==========================================================================
// Exports & Helpers
// ==========================================================================
function handleExportCsv() {
  if (!state.activeData || !state.activeData.forecast_data) return;

  const data = state.activeData.forecast_data;
  const headers = [
    "datetime",
    "timestamp",
    "M6_Best_Ensemble",
    "ci_50_lower",
    "ci_50_upper",
    "ci_80_lower",
    "ci_80_upper",
    "ci_95_lower",
    "ci_95_upper",
    "M1_Holt_Damped",
    "M2_Fourier_Harmonic",
    "M3_Kalman_OU",
    "M4_ARX_Ridge",
    "M5_kNN_Analog",
  ];

  let csv = headers.join(",") + "\n";
  data.forEach((r) => {
    const row = headers.map((h) => r[h] !== undefined ? r[h] : "");
    csv += row.join(",") + "\n";
  });

  const sym = state.activeData.metadata?.symbol || "crypto";
  const ts = getFormattedTimestamp();
  const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
  triggerBlobDownload(blob, `forecast_${sym}_${state.horizonSteps}steps_${ts}.csv`);
  showToast("File CSV berhasil diekspor!", "success");
}

function handleExportJson() {
  if (!state.activeData) return;
  const sym = state.activeData.metadata?.symbol || "crypto";
  const ts = getFormattedTimestamp();
  const jsonStr = JSON.stringify(state.activeData, null, 2);
  const blob = new Blob([jsonStr], { type: "application/json" });
  triggerBlobDownload(blob, `forecast_summary_${sym}_${ts}.json`);
  showToast("File JSON berhasil diekspor!", "success");
}

function formatPrice(val) {
  if (val === undefined || val === null || isNaN(val)) return "0.00";
  if (val >= 1000) {
    return val.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  }
  return val.toFixed(4);
}

function formatModelName(key) {
  const map = {
    M1_Holt_Damped: "M1 Holt-Winters",
    M2_Fourier_Harmonic: "M2 Fourier FFT",
    M3_Kalman_OU: "M3 Kalman OU",
    M4_ARX_Ridge: "M4 ARX-Ridge",
    M5_kNN_Analog: "M5 k-NN Analog",
    M6_Best_Ensemble: "M6 Best Ensemble",
  };
  return map[key] || key;
}

function formatDateTime(dtStr) {
  if (!dtStr) return "--";
  const dt = new Date(dtStr);
  return dt.toLocaleString("id-ID", {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function showLoading(msg) {
  elements.loadingMessage.textContent = msg || "Memproses...";
  elements.loadingOverlay.classList.add("active");
}

function hideLoading() {
  elements.loadingOverlay.classList.remove("active");
}

function showToast(msg, type = "success") {
  const toast = document.createElement("div");
  toast.className = `toast toast-${type}`;
  toast.textContent = msg;
  elements.toastContainer.appendChild(toast);

  setTimeout(() => {
    toast.style.opacity = "0";
    toast.style.transform = "translateX(100%)";
    setTimeout(() => toast.remove(), 300);
  }, 4000);
}
