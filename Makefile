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

.PHONY: help setup install run collect forecast web test clean

help:
	@echo ""
	@echo "⚡ Crypto Predictor - Perintah Makefile:"
	@echo "────────────────────────────────────────────────────────────────────────"
	@echo "  make setup          Siapkan virtual environment & install dependensi"
	@echo "  make run            Tampilkan bantuan & daftar sub-fitur (main.py)"
	@echo "  make web            Jalankan antarmuka dashboard web (port $(PORT))"
	@echo "  make forecast       Jalankan peramalan kuantitatif pada dataset JSON"
	@echo "                      Contoh: make forecast FILE=data/ETHUSDT_15m_1d.json"
	@echo "  make collect        Jalankan sub-fitur pengumpul data Binance"
	@echo "                      Contoh: make collect SYMBOL=ETH TF=15m DAYS=1"
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

collect: setup
	@$(PYTHON) main.py collect -s $(SYMBOL) -t $(TF) -d $(DAYS)

test: setup
	@$(PYTHON) -m unittest discover tests

clean:
	@rm -rf __pycache__ src/__pycache__ src/collector/__pycache__ tests/__pycache__ .pytest_cache
	@echo "✅ Cache dibersihkan."
