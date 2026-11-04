# ============================================================================
# Crypto Predictor - Makefile
# ============================================================================

VENV := .venv
PYTHON := $(VENV)/bin/python3
PIP := $(VENV)/bin/pip

SYMBOL ?= ETH
TF ?= 15m
DAYS ?= 1
HORIZON ?= 48
FILE ?= data/ETHUSDT_15m_1d.json
PORT ?= 8000
BACK ?= 24
TOP_COINS ?= BTC ETH SOL BNB XRP DOGE ADA TRX AVAX SUI LINK 1000SHIB LTC DOT BCH UNI NEAR APT 1000PEPE ICP
TIMEFRAMES ?= 15m 1h 4h 1d

.PHONY: help setup install run collect collect-top forecast replay pdf web test clean

help:
	@echo ""
	@echo "⚡ Crypto Predictor - Perintah Makefile:"
	@echo "────────────────────────────────────────────────────────────────────────"
	@echo "  make setup          Siapkan virtual environment & install dependensi"
	@echo "  make run            Tampilkan bantuan & daftar sub-fitur (main.py)"
	@echo "  make web            Jalankan antarmuka dashboard web (port $(PORT))"
	@echo "  make forecast       Jalankan peramalan kuantitatif pada dataset JSON"
	@echo "                      Contoh: make forecast FILE=data/ETHUSDT_15m_1d.json"
	@echo "  make replay         Uji waktu mundur (historical cutoff replay backtest)"
	@echo "                      Contoh: make replay FILE=data/BTCUSDT_1h_30d_...json BACK=24"
	@echo "  make pdf            Buat laporan analisis PDF kuantitatif eksekutif"
	@echo "  make collect        Jalankan sub-fitur pengumpul data Binance"
	@echo "                      Contoh: make collect SYMBOL=ETH TF=15m DAYS=1"
	@echo "  make collect-top    Kumpulkan data untuk 20 koin teratas & semua TF"
	@echo "                      Contoh: make collect-top DAYS=30"
	@echo "  make test           Jalankan unit tests"
	@echo "  make clean          Bersihkan file cache Python"
	@echo "────────────────────────────────────────────────────────────────────────"
	@echo ""

$(VENV)/bin/activate: requirements.txt
	@if [ ! -d "$(VENV)" ]; then \
		echo "📦 Membuat virtual environment di $(VENV)..."; \
		python3 -m venv $(VENV); \
	fi
	@echo "📦 Menginstal dependensi..."; \
	$(PIP) install -r requirements.txt
	@touch $(VENV)/bin/activate

setup: $(VENV)/bin/activate
	@echo "✅ Environment siap digunakan!"

install: setup

run: setup
	@$(PYTHON) main.py

web: setup
	@$(PYTHON) main.py web --port $(PORT)

forecast: setup
	@$(PYTHON) main.py forecast --input $(FILE) --horizon $(HORIZON)

replay: setup
	@$(PYTHON) main.py replay --input $(FILE) --back $(BACK)

pdf: setup
	@$(PYTHON) scripts/generate_pdf_report.py

collect: setup
	@$(PYTHON) main.py collect -s $(SYMBOL) -t $(TF) -d $(DAYS)

collect-top: setup
	@echo "🚀 Memulai pengumpulan data untuk $(words $(TOP_COINS)) koin teratas x $(words $(TIMEFRAMES)) timeframe ($(DAYS) hari)..."
	@for coin in $(TOP_COINS); do \
		for tf in $(TIMEFRAMES); do \
			$(MAKE) collect SYMBOL=$$coin TF=$$tf DAYS=$(DAYS); \
			sleep 0.2; \
		done; \
	done
	@echo "✅ Semua dataset berhasil dikumpulkan ke direktori data/!"

test: setup
	@$(PYTHON) -m unittest discover tests

clean:
	@rm -rf __pycache__ src/__pycache__ src/collector/__pycache__ tests/__pycache__ .pytest_cache
	@echo "✅ Cache dibersihkan."
