# ⚡ Crypto Market Data Collector (Free Tier)

Sistem pengumpul data pasar cryptocurrency historis berbasis Python yang mengintegrasikan data **OHLCV**, **Indikator Teknikal (RSI, MACD, EMA)**, serta data derivatif (**Funding Rate** & **Open Interest**).

Data diekspor dalam format **Raw JSON** terstruktur yang siap digunakan untuk backtesting, analisis kuantitatif, machine learning, atau visualisasi TradingView.

---

## 🌟 Fitur Utama

1. **Aset Fleksibel**: Mendukung koin utama (`BTC`, `ETH`, `SOL`, `BNB`) maupun altcoin populer lainnya (`DOGE`, `SUI`, `XRP`, `ADA`, `PEPE`, dsb). Otomatis menormalisasi input (misal `btc` -> `BTCUSDT`).
2. **Timeframe Sesuai Kebutuhan**: Pilihan interval `15m`, `4h`, dan `1d`.
3. **Periode Historis 3 Bulan (90 Hari)**: Otomatis membagi permintaan dengan sistem pagination cerdas.
4. **Data Lengkap yang Dikumpulkan**:
   - **OHLCV**: Open, High, Low, Close, Volume (Base & Quote USD), Trades Count.
   - **RSI (14)**: Dihitung menggunakan *Wilder's Smoothing (RMA)* standar TradingView.
   - **MACD (12, 26, 9)**: MACD Line, Signal Line, dan Histogram.
   - **EMA (Exponential Moving Average)**: EMA 20, EMA 50, dan EMA 200.
   - **Funding Rate**: Timestamp settlement, rate persentase, dan mark price.
   - **Open Interest**: Total kontrak/koin terbuka & nilai nominal dalam USD.
5. **Warm-up Lookback Buffer**: Mengambil 200 candle ekstra di awal periode secara otomatis agar perhitungan RSI dan EMA 200 di hari pertama periode 90 hari sudah stabil dan tidak bernilai `null` (zero distortion).
6. **Built-in DNS-over-HTTPS (DoH)**: Mengatasi pemblokiran DNS / Internet Positif ISP di Indonesia (Indosat, Telkomsel, XL, dsb) secara otomatis menggunakan Cloudflare/Google DoH tanpa memerlukan VPN pihak ketiga.
7. **Free Tier API (100% Gratis & Tanpa API Key)**:
   - **Binance Futures API** (`fapi.binance.com`): Likuiditas tertinggi dunia, pagination cepat (hingga 1.500 candle per call).
   - **Bybit Futures API** (`api.bybit.com`): Mendukung riwayat Open Interest penuh 90+ hari.
8. **Interactive CLI & Web Dashboard**: Disertai mode wizard interaktif di terminal dan Web Dashboard modern berbasis TradingView Lightweight Charts.

---

## 📁 Struktur Direktori

```text
market-data-collector/
├── data/                       # Direktori hasil ekspor data (JSON & CSV)
├── src/
│   ├── collectors/             # Modul pengumpul API
│   │   ├── base.py             # Interface & data merger
│   │   ├── binance.py          # Binance USD-M Futures collector
│   │   └── bybit.py            # Bybit v5 Linear Futures collector
│   ├── indicators/             # Kalkulator indikator teknikal
│   │   └── calculator.py       # RSI, MACD, EMA 20/50/200
│   ├── network/                # Jaringan & anti-blocking
│   │   └── doh.py              # DNS-over-HTTPS resolver
│   ├── storage/                # Serialisasi & ekspor file
│   │   └── exporter.py         # Format JSON & CSV
│   ├── web/                    # Dashboard visualisasi interaktif
│   │   ├── index.html
│   │   ├── app.js
│   │   └── style.css
│   └── config.py               # Konfigurasi sistem
├── tests/
│   └── test_collector.py       # Unit test validasi indikator & API
├── main.py                     # Entry point CLI
├── run.sh                      # Shell script runner
├── requirements.txt            # Dependensi Python
└── README.md
```

---

## 🚀 Panduan Penggunaan

### 1. Instalasi Lingkungan
Pastikan Python 3.10+ terpasang:
```bash
# Menggunakan run.sh (otomatis membuat .venv dan menginstal dependencies)
./run.sh --help
```
Atau manual:
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

---

### 1. Manajemen Service Menggunakan Makefile (Direkomendasikan)

Tersedia [`Makefile`](file:///home/iamyourdre/Development/iamyourdre/crypto/market-data-collector/Makefile) lengkap untuk mengontrol seluruh alur kerja:

```bash
# 1. Setup otomatis virtual environment & dependencies
make setup

# 2. Menjalankan CLI wizard interaktif pengumpul data
make run

# 3. Mengumpulkan data langsung dengan parameter cepat
make collect SYMBOL=BTC TF=15m DAYS=90 SOURCE=binance
make collect SYMBOL=SOL TF=4h DAYS=90 SOURCE=bybit CSV=1

# 4. Manajemen Web Dashboard Service (Background Daemon)
make start     # Menjalankan Web Dashboard di background (port 8080)
make status    # Mengecek status service (Running / Stopped, PID, URL)
make logs      # Melihat log service secara real-time
make stop      # Menghentikan service
make restart   # Restart service

# 5. Testing & Cleanup
make test      # Menjalankan unit tests
make clean     # Membersihkan cache & temporary files
```

---

### 2. Mode Web Dashboard Interaktif

Setelah menjalankan `make start`, dashboard langsung aktif di **`http://localhost:8080`**.

Fitur dashboard:
- **Dataset Selector Dropdown**: Otomatis mendeteksi semua file JSON yang ada di folder `data/` dan dapat berganti koin/timeframe secara instan.
- **Chart Candlestick**: Tersinkronisasi dengan EMA 20, 50, 200 & Volume.
- **Sub-chart RSI (14)**: Dengan batas overbought (70) dan oversold (30).
- **Sub-chart MACD (12, 26, 9)**: Dengan batang histogram warna dinamis (hijau/merah).
- **Sub-chart Open Interest & Funding Rate**: Menampilkan tren likuiditas kontrak derivatif.
- **Tab Raw JSON Data**: Dengan fitur pencarian instan dan tombol copy ke clipboard.
- **Upload / Drag & Drop**: Bisa memuat file JSON lokal secara langsung.

Hentikan service kapan saja dengan:
```bash
make stop
```

---

## 📊 Struktur Format JSON Output

File JSON yang dihasilkan (`data/<SYMBOL>_<TF>_<SOURCE>_<DAYS>d.json`) memiliki format terstruktur:

```json
{
  "metadata": {
    "symbol": "BTCUSDT",
    "exchange": "binance",
    "timeframe": "4h",
    "period_days": 90,
    "start_time": "2026-08-03T00:00:00Z",
    "end_time": "2026-11-01T06:00:00Z",
    "total_candles": 540,
    "total_funding_events": 270,
    "total_oi_records": 174,
    "indicators_config": {
      "rsi_period": 14,
      "macd": { "fast": 12, "slow": 26, "signal": 9 },
      "ema_periods": [20, 50, 200]
    },
    "summary_stats": {
      "start_price": 64320.5,
      "latest_price": 77983.2,
      "highest_price": 87385.1,
      "lowest_price": 62268.2,
      "price_change_pct": 21.24,
      "total_volume": 1284592.4,
      "latest_rsi": 43.69,
      "latest_funding_rate": 0.0001,
      "latest_open_interest": 96888.21
    },
    "generated_at": "2026-11-01T07:00:00Z"
  },
  "data": [
    {
      "timestamp": 1785744000000,
      "datetime": "2026-08-03T08:00:00Z",
      "open": 64250.0,
      "high": 64800.0,
      "low": 64100.0,
      "close": 64650.5,
      "volume": 14210.5,
      "quote_volume": 915820430.2,
      "trades_count": 314205,
      "indicators": {
        "rsi_14": 52.84,
        "macd": {
          "line": 124.5,
          "signal": 118.2,
          "hist": 6.3
        },
        "ema_20": 64100.2,
        "ema_50": 63850.4,
        "ema_200": 62900.1
      },
      "derivatives": {
        "funding_rate": 0.0001,
        "funding_settled": 0.0001,
        "open_interest": 93229.44,
        "open_interest_usd": 6027329100.0
      }
    }
  ],
  "raw_series": {
    "funding_rates": [
      {
        "timestamp": 1785744000000,
        "datetime": "2026-08-03T08:00:00Z",
        "funding_rate": 0.0001,
        "mark_price": 64650.0
      }
    ],
    "open_interest": [
      {
        "timestamp": 1785744000000,
        "datetime": "2026-08-03T08:00:00Z",
        "open_interest": 93229.44,
        "open_interest_usd": 6027329100.0
      }
    ]
  }
}
```

---

## 🧪 Menjalankan Pengujian (Testing)

Proyek dilengkapi unit test yang memvalidasi keakuratan matematis indikator RSI, MACD, EMA serta koneksi live API:

```bash
python3 -m unittest tests/test_collector.py
```
Hasil uji:
- Verifikasi formula RSI Wilder's Smoothing (RMA) dan batasan `0 <= RSI <= 100`.
- Verifikasi formula MACD (`Histogram = Line - Signal`).
- Verifikasi EMA urutan tren (`EMA 20 > EMA 50 > EMA 200` pada steady uptrend).
- Live API connectivity test untuk Binance & Bybit.
