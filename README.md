# ⚡ Crypto Predictor System

Sistem terstruktur dan modular untuk analisis kuantitatif dan prediksi pasar cryptocurrency multi-metode dengan antarmuka web interaktif (TradingView-style charts, GARCH volatility cones, & Monte Carlo barrier simulator).

---

## 📁 Struktur Direktori

```text
crypto-predictor/
├── data/                            # Dataset historis JSON (OHLCV, funding rate, open interest)
│   ├── ETHUSDT_15m_1d.json          # Contoh dataset 15m (1 hari = 96 candles)
│   └── BTCUSDT_1h_2d.json           # Contoh dataset 1 jam (2 hari = 48 candles)
├── src/
│   ├── collector/                   # Sub-fitur 1: Market Data Collector Binance Futures
│   │   ├── binance.py               # Binance Futures API client & DoH resolver
│   │   └── __init__.py
│   └── web_server.py                # Server FastAPI & REST API untuk antarmuka web
├── web/                             # Sub-fitur 2: Web Dashboard Interaktif
│   ├── index.html                   # HTML5 layout dengan dark glassmorphism
│   ├── style.css                    # Vanilla CSS design system modern
│   └── app.js                       # Canvas chart engine, HUD, & live data fetcher
├── tests/                           # Unit & integration tests
│   ├── test_collector.py
│   ├── test_forecast_engine.py
│   └── test_web_server.py
├── crypto_forecast_engine.py        # Core Engine: 6-stage quantitative forecasting
├── main.py                          # Entry point CLI (collect, forecast, web)
├── requirements.txt                 # Dependensi Python
├── Makefile                         # Shortcut perintah kerja
└── README.md
```

---

## 🚀 Panduan Penggunaan

### 1. Instalasi Environment

Pastikan Python 3.10+ terpasang, lalu siapkan virtual environment:

```bash
make setup
```

Atau manual:
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

---

### 2. Antarmuka Web Interaktif (Web Dashboard)

Untuk menjalankan antarmuka web interaktif dengan visualisasi chart candlestick, trajectory proyeksi, GARCH confidence cones, serta simulator barrier Monte Carlo:

```bash
make web
# atau
python main.py web --port 8000
```

Buka peramban di: **http://127.0.0.1:8000**

#### Fitur Web Dashboard:
- **Interactive Multi-Method Chart**: Grafik candlestick historis + proyeksi masa depan dengan pembagi zona waktu ("NOW").
- **5 Base Models + M6 Ensemble**:
  - `M1`: Holt-Winters Damped Trend
  - `M2`: Spectral Fourier Harmonic FFT
  - `M3`: Dual-State Kalman Filter + OU Equilibrium
  - `M4`: ARX-Ridge Exogenous Multi-Horizon
  - `M5`: Non-Parametric Weighted k-NN Analog Trajectory
  - `M6`: Best Simplex-Optimized Ensemble
- **GARCH(1,1) Volatility Cones**: Pita interval kepercayaan 50%, 80%, dan 95%.
- **First-Passage Barrier Probability Matrix**: Probabilitas sentuh target upside (+0.5% s/d +5%) dan downside support (-0.5% s/d -5%) berbasis 10.000 simulasi Student-t Monte Carlo.
- **Kalkulator Barrier Kustom**: Input target harga arbitrer (contoh: `$2,350`) dan hitung probabilitasnya seketika.
- **Sub-Charts Terpadu**: RSI-14, MACD, Order Flow CVD (Cumulative Volume Delta), & Open Interest.
- **Live Binance Data Fetcher**: Tarik data fresh secara live dari Binance Futures untuk koin apa pun (ETH, BTC, SOL, dll.) dan langsung jalankan peramalan.
- **Export Data**: Unduh trajectory hasil ramalan ke CSV atau ringkasan JSON.

---

### 3. Peramalan Kuantitatif via CLI (`forecast`)

Jalankan engine peramalan langsung pada file dataset JSON:

```bash
# Peramalan default pada ETHUSDT 15m (1 hari)
python main.py forecast --input data/ETHUSDT_15m_1d.json --horizon 48

# Menggunakan target Makefile
make forecast FILE=data/ETHUSDT_15m_1d.json HORIZON=48
```

Output:
- `forecast_trajectories.csv`: Proyeksi harga per langkah waktu beserta batas bawah/atas CI.
- `forecast_summary.json`: Bobot model ensemble, metrik backtest (RMSE, MAE, MAPE, Directional Accuracy), dan probabilitas barrier Monte Carlo.

---

### 4. Kolektor Data Pasar Historis (`collect`)

Ambil data candlestick OHLCV, Funding Rate, dan Open Interest dari Binance Futures:

```bash
# Contoh: ETHUSDT timeframe 15m selama 1 hari
python main.py collect -s ETH -t 15m -d 1

# Atau via Makefile
make collect SYMBOL=ETH TF=15m DAYS=1
```

---

### 5. Menjalankan Unit Tests

```bash
make test
# atau
python -m unittest discover tests
```

---

## 🔬 Metodologi Kuantitatif

1. **Stage 1: Normalisasi Skema & Imputasi Indikator**: Secara otomatis menghitung indikator teknikal (EMA 20/50/200, RSI 14, MACD) secara kausal jika tidak tersedia dalam dataset mentah.
2. **Stage 2: Feature Engineering Eksogen**: 18 fitur teknikal kausal, termasuk CVD order flow, rasio volume, Bollinger Bands Z-score, dan harmonik diurnal 24 jam.
3. **Stage 3: 5 Model Peramalan Lintas Paradigma**: Menggabungkan smoothing parametrik, spectral FFT bandpass, filter Kalman status ganda, regresi ridge multi-langkah, dan analog non-parametrik k-NN.
4. **Stage 4: Validasi Walk-Forward & Optimasi Simplex**: Pembobotan dinamis berbasis akurasi arah (Directional Accuracy) dan RMSE out-of-sample yang adaptif terhadap panjang data.
5. **Stage 5: Conditional Volatility GARCH(1,1)**: Memodelkan heteroskedastisitas bersyarat dan memproyeksikan kerucut dispersi sub-difusif.
6. **Stage 6: Barrier Simulator Student-t Monte Carlo**: 10.000 jalur inovasi fat-tailed untuk mengestimasi peluang first-passage hitting price level.
