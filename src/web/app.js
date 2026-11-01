/**
 * Crypto Market Data Dashboard - Interactive Visualization
 * Powered by TradingView Lightweight Charts
 */

let globalData = null;
let priceChart = null;
let rsiChart = null;
let macdChart = null;
let derivChart = null;

const darkTheme = {
  layout: {
    background: { color: '#121824' },
    textColor: '#94a3b8',
    fontFamily: 'Inter, sans-serif',
  },
  grid: {
    vertLines: { color: '#1e293b' },
    horzLines: { color: '#1e293b' },
  },
  crosshair: {
    vertLine: { color: '#475569', width: 1, style: 2 },
    horzLine: { color: '#475569', width: 1, style: 2 },
  },
  timeScale: {
    borderColor: '#243247',
    timeVisible: true,
    secondsVisible: false,
  },
};

// Initialize All Charts
function initCharts() {
  const priceContainer = document.getElementById('priceChartContainer');
  const rsiContainer = document.getElementById('rsiChartContainer');
  const macdContainer = document.getElementById('macdChartContainer');
  const derivContainer = document.getElementById('derivativesChartContainer');

  priceContainer.innerHTML = '';
  rsiContainer.innerHTML = '';
  macdContainer.innerHTML = '';
  derivContainer.innerHTML = '';

  const width = priceContainer.clientWidth;

  // 1. Price Chart
  priceChart = LightweightCharts.createChart(priceContainer, {
    ...darkTheme,
    width: width,
    height: 380,
    rightPriceScale: { borderColor: '#243247' },
  });

  // 2. RSI Chart
  rsiChart = LightweightCharts.createChart(rsiContainer, {
    ...darkTheme,
    width: width,
    height: 180,
    rightPriceScale: { borderColor: '#243247', scaleMargins: { top: 0.1, bottom: 0.1 } },
  });

  // 3. MACD Chart
  macdChart = LightweightCharts.createChart(macdContainer, {
    ...darkTheme,
    width: width,
    height: 180,
    rightPriceScale: { borderColor: '#243247' },
  });

  // 4. Derivatives Chart
  derivChart = LightweightCharts.createChart(derivContainer, {
    ...darkTheme,
    width: width,
    height: 180,
    rightPriceScale: { borderColor: '#243247' },
  });

  // Synchronize time scales
  const charts = [priceChart, rsiChart, macdChart, derivChart];
  charts.forEach((c1) => {
    c1.timeScale().subscribeVisibleLogicalRangeChange((range) => {
      charts.forEach((c2) => {
        if (c1 !== c2 && range) {
          c2.timeScale().setVisibleLogicalRange(range);
        }
      });
    });
  });

  window.addEventListener('resize', () => {
    const newWidth = priceContainer.clientWidth;
    charts.forEach((c) => c.applyOptions({ width: newWidth }));
  });
}

function renderData(data) {
  if (!data || !data.data || data.data.length === 0) return;
  globalData = data;

  // Update Header Badges
  const meta = data.metadata || {};
  document.getElementById('headerTitle').innerText = `${meta.symbol || 'CRYPTO'} Market Data Analysis`;
  document.getElementById('badgeExchange').innerText = (meta.exchange || 'BINANCE').toUpperCase();
  document.getElementById('badgeSymbol').innerText = meta.symbol || 'COIN';
  document.getElementById('badgeTimeframe').innerText = meta.timeframe || '15m';
  document.getElementById('badgeCandles').innerText = `${data.data.length} CANDLES`;

  // Update Stats
  const stats = meta.summary_stats || {};
  document.getElementById('statPrice').innerText = `$${(stats.latest_price || 0).toLocaleString(undefined, { minimumFractionDigits: 2 })}`;
  const change = stats.price_change_pct || 0;
  const changeEl = document.getElementById('statPriceChange');
  changeEl.innerText = `${change >= 0 ? '+' : ''}${change.toFixed(2)}% (90d)`;
  changeEl.style.color = change >= 0 ? 'var(--bullish)' : 'var(--bearish)';

  document.getElementById('statRange').innerText = `$${(stats.lowest_price || 0).toLocaleString()} - $${(stats.highest_price || 0).toLocaleString()}`;

  const latestRsi = stats.latest_rsi || 50;
  document.getElementById('statRSI').innerText = latestRsi.toFixed(2);
  const rsiLabelEl = document.getElementById('statRSILabel');
  if (latestRsi >= 70) {
    rsiLabelEl.innerText = 'Overbought (>70)';
    rsiLabelEl.style.color = 'var(--bearish)';
  } else if (latestRsi <= 30) {
    rsiLabelEl.innerText = 'Oversold (<30)';
    rsiLabelEl.style.color = 'var(--bullish)';
  } else {
    rsiLabelEl.innerText = 'Neutral (30-70)';
    rsiLabelEl.style.color = 'var(--text-dim)';
  }

  const lastCandle = data.data[data.data.length - 1];
  const macdObj = lastCandle.indicators?.macd || {};
  document.getElementById('statMACD').innerText = (macdObj.line || 0).toFixed(2);
  document.getElementById('statMACDHist').innerText = `Hist: ${(macdObj.hist || 0).toFixed(2)} | Sig: ${(macdObj.signal || 0).toFixed(2)}`;

  const funding = stats.latest_funding_rate !== null ? stats.latest_funding_rate : (lastCandle.derivatives?.funding_rate || 0);
  const fundEl = document.getElementById('statFunding');
  fundEl.innerText = `${(funding * 100).toFixed(4)}%`;
  fundEl.style.color = funding >= 0 ? 'var(--bullish)' : 'var(--bearish)';

  const oi = stats.latest_open_interest !== null ? stats.latest_open_interest : (lastCandle.derivatives?.open_interest || 0);
  document.getElementById('statOI').innerText = oi.toLocaleString(undefined, { maximumFractionDigits: 2 });

  initCharts();

  // Helper functions for compatibility across Lightweight Charts v4 and v5
  const addCandlestick = (chart, opt) =>
    typeof chart.addCandlestickSeries === 'function'
      ? chart.addCandlestickSeries(opt)
      : chart.addSeries(LightweightCharts.CandlestickSeries, opt);

  const addLine = (chart, opt) =>
    typeof chart.addLineSeries === 'function'
      ? chart.addLineSeries(opt)
      : chart.addSeries(LightweightCharts.LineSeries, opt);

  const addHistogram = (chart, opt) =>
    typeof chart.addHistogramSeries === 'function'
      ? chart.addHistogramSeries(opt)
      : chart.addSeries(LightweightCharts.HistogramSeries, opt);

  // 1. Populate Candlesticks & Volume & EMAs
  const candleSeries = addCandlestick(priceChart, {
    upColor: '#10b981',
    downColor: '#ef4444',
    borderVisible: false,
    wickUpColor: '#10b981',
    wickDownColor: '#ef4444',
  });

  const volumeSeries = addHistogram(priceChart, {
    color: '#334155',
    priceFormat: { type: 'volume' },
    priceScaleId: '',
    scaleMargins: { top: 0.8, bottom: 0 },
  });

  const ema20Series = addLine(priceChart, { color: '#38bdf8', lineWidth: 2 });
  const ema50Series = addLine(priceChart, { color: '#f59e0b', lineWidth: 2 });
  const ema200Series = addLine(priceChart, { color: '#ec4899', lineWidth: 2 });

  const candleData = [];
  const volumeData = [];
  const ema20Data = [];
  const ema50Data = [];
  const ema200Data = [];

  // 2. Populate RSI
  const rsiSeries = addLine(rsiChart, { color: '#a855f7', lineWidth: 2 });
  const rsiData = [];

  // Add 70 and 30 baseline guides
  addLine(rsiChart, { color: '#ef4444', lineWidth: 1, lineStyle: 2 }).setData(
    data.data.map(d => ({ time: Math.floor(d.timestamp / 1000), value: 70 }))
  );
  addLine(rsiChart, { color: '#10b981', lineWidth: 1, lineStyle: 2 }).setData(
    data.data.map(d => ({ time: Math.floor(d.timestamp / 1000), value: 30 }))
  );

  // 3. Populate MACD
  const macdHistSeries = addHistogram(macdChart, { priceScaleId: 'right' });
  const macdLineSeries = addLine(macdChart, { color: '#38bdf8', lineWidth: 2 });
  const macdSigSeries = addLine(macdChart, { color: '#f59e0b', lineWidth: 1 });
  const macdHistData = [];
  const macdLineData = [];
  const macdSigData = [];

  // 4. Populate Derivatives
  const oiSeries = addLine(derivChart, { color: '#a855f7', lineWidth: 2 });
  const oiData = [];

  data.data.forEach((row) => {
    const t = Math.floor(row.timestamp / 1000);

    candleData.push({ time: t, open: row.open, high: row.high, low: row.low, close: row.close });

    const isUp = row.close >= row.open;
    volumeData.push({ time: t, value: row.volume || 0, color: isUp ? '#065f46' : '#7f1d1d' });

    const inds = row.indicators || {};
    if (inds.ema_20 !== null && inds.ema_20 !== undefined) ema20Data.push({ time: t, value: inds.ema_20 });
    if (inds.ema_50 !== null && inds.ema_50 !== undefined) ema50Data.push({ time: t, value: inds.ema_50 });
    if (inds.ema_200 !== null && inds.ema_200 !== undefined) ema200Data.push({ time: t, value: inds.ema_200 });

    const rsiVal = inds.rsi_14 ?? inds.rsi;
    if (rsiVal !== null && rsiVal !== undefined) rsiData.push({ time: t, value: rsiVal });

    if (inds.macd) {
      if (inds.macd.line !== null) macdLineData.push({ time: t, value: inds.macd.line });
      if (inds.macd.signal !== null) macdSigData.push({ time: t, value: inds.macd.signal });
      if (inds.macd.hist !== null) {
        macdHistData.push({
          time: t,
          value: inds.macd.hist,
          color: inds.macd.hist >= 0 ? '#10b981' : '#ef4444',
        });
      }
    }

    const deriv = row.derivatives || {};
    if (deriv.open_interest !== null && deriv.open_interest !== undefined) {
      oiData.push({ time: t, value: deriv.open_interest });
    }
  });

  candleSeries.setData(candleData);
  volumeSeries.setData(volumeData);
  ema20Series.setData(ema20Data);
  ema50Series.setData(ema50Data);
  ema200Series.setData(ema200Data);

  rsiSeries.setData(rsiData);

  macdHistSeries.setData(macdHistData);
  macdLineSeries.setData(macdLineData);
  macdSigSeries.setData(macdSigData);

  if (oiData.length > 0) {
    oiSeries.setData(oiData);
  }

  // Update Raw JSON view
  document.getElementById('jsonDisplay').innerText = JSON.stringify(data, null, 2);
}

// Tab Switching
function switchTab(tab) {
  const chartsView = document.getElementById('chartsView');
  const jsonView = document.getElementById('jsonView');
  const tabCharts = document.getElementById('tabCharts');
  const tabJson = document.getElementById('tabJson');

  if (tab === 'charts') {
    chartsView.style.display = 'flex';
    jsonView.style.display = 'none';
    tabCharts.classList.add('active');
    tabJson.classList.remove('active');
  } else {
    chartsView.style.display = 'none';
    jsonView.style.display = 'flex';
    tabCharts.classList.remove('active');
    tabJson.classList.add('active');
  }
}

// Copy JSON
function copyJson() {
  if (!globalData) return;
  navigator.clipboard.writeText(JSON.stringify(globalData, null, 2)).then(() => {
    alert('JSON copied to clipboard!');
  });
}

// Download clean JSON
document.getElementById('btnDownloadJson').addEventListener('click', () => {
  if (!globalData) return;
  const blob = new Blob([JSON.stringify(globalData, null, 2)], { type: 'application/json' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `${globalData.metadata?.symbol || 'crypto'}_${globalData.metadata?.timeframe || '15m'}.json`;
  a.click();
  URL.revokeObjectURL(url);
});

// File Upload Handler
document.getElementById('fileInput').addEventListener('change', (e) => {
  const file = e.target.files[0];
  if (!file) return;
  const reader = new FileReader();
  reader.onload = (event) => {
    try {
      const data = JSON.parse(event.target.result);
      renderData(data);
    } catch (err) {
      alert('Error parsing JSON: ' + err.message);
    }
  };
  reader.readAsText(file);
});

// Auto-load available datasets from /api/datasets and populate dropdown
async function loadDatasets() {
  const select = document.getElementById('datasetSelect');
  try {
    const resp = await fetch('/api/datasets');
    if (resp.ok) {
      const files = await resp.json();
      select.innerHTML = '';
      if (files.length === 0) {
        select.innerHTML = '<option value="">No datasets found</option>';
        return;
      }

      files.forEach((file, idx) => {
        const opt = document.createElement('option');
        opt.value = file.path;
        opt.innerText = `${file.filename} (${file.size_kb} KB)`;
        select.appendChild(opt);
      });

      // Load the first (most recent) dataset
      loadDatasetPath(files[0].path);

      select.addEventListener('change', (e) => {
        if (e.target.value) {
          loadDatasetPath(e.target.value);
        }
      });
      return;
    }
  } catch (e) {
    console.debug('Failed to fetch /api/datasets:', e);
  }

  // Fallback to sample file if /api/datasets not available
  loadDatasetPath('/data/BTCUSDT_4h_binance_90d.json');
}

async function loadDatasetPath(path) {
  try {
    const resp = await fetch(path);
    if (resp.ok) {
      const data = await resp.json();
      renderData(data);
    }
  } catch (err) {
    console.error('Error loading dataset from ' + path, err);
  }
}

window.addEventListener('DOMContentLoaded', () => {
  loadDatasets();
});
