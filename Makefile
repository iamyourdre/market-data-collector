# ============================================================================
# Crypto Market Data Collector - Makefile
# ============================================================================

VENV := .venv
PYTHON := $(VENV)/bin/python3
PIP := $(VENV)/bin/pip
PID_FILE := .dashboard.pid
LOG_FILE := dashboard.log
PORT ?= 8080

# Default parameters for data collection
SYMBOL ?= BTC
TF ?= 15m
DAYS ?= 90
SOURCE ?= binance
CSV ?= 0

.PHONY: help setup install run interactive collect start stop restart status logs test clean

# ----------------------------------------------------------------------------
# Help / Default Target
# ----------------------------------------------------------------------------
help:
	@echo ""
	@echo "⚡ Crypto Market Data Collector - Makefile Commands:"
	@echo "────────────────────────────────────────────────────────────────────────"
	@echo "  make setup            Setup environment virtualenv & install dependencies"
	@echo "  make run              Jalankan CLI interaktif untuk mengumpulkan data"
	@echo "  make collect          Kumpulkan data langsung dengan parameter"
	@echo "                        (Contoh: make collect SYMBOL=ETH TF=4h DAYS=90 SOURCE=binance CSV=1)"
	@echo "────────────────────────────────────────────────────────────────────────"
	@echo "  make start            Jalankan Web Dashboard Service di background"
	@echo "  make stop             Hentikan Web Dashboard Service"
	@echo "  make restart          Restart Web Dashboard Service"
	@echo "  make status           Periksa status Web Dashboard Service"
	@echo "  make logs             Lihat log output Web Dashboard secara real-time"
	@echo "────────────────────────────────────────────────────────────────────────"
	@echo "  make test             Jalankan unit tests & validasi indikator"
	@echo "  make clean            Bersihkan cache Python & log files"
	@echo "────────────────────────────────────────────────────────────────────────"
	@echo ""

# ----------------------------------------------------------------------------
# Environment Setup
# ----------------------------------------------------------------------------
$(VENV)/bin/activate: requirements.txt
	@if [ ! -d "$(VENV)" ]; then \
		echo "📦 Creating virtual environment in $(VENV)..."; \
		python3 -m venv $(VENV); \
	fi
	@echo "📦 Installing / updating dependencies..."; \
	$(PIP) install --upgrade pip > /dev/null 2>&1 || true; \
	$(PIP) install -r requirements.txt
	@touch $(VENV)/bin/activate

setup: $(VENV)/bin/activate
	@echo "✅ Environment siap digunakan!"

install: setup

# ----------------------------------------------------------------------------
# Data Collector (CLI)
# ----------------------------------------------------------------------------
run: setup
	@$(PYTHON) main.py

interactive: run

collect: setup
	@CSV_FLAG=""; \
	if [ "$(CSV)" = "1" ] || [ "$(CSV)" = "true" ]; then \
		CSV_FLAG="--csv"; \
	fi; \
	$(PYTHON) main.py -s $(SYMBOL) -t $(TF) -d $(DAYS) --source $(SOURCE) $$CSV_FLAG

# ----------------------------------------------------------------------------
# Web Dashboard Service Management (Background Service)
# ----------------------------------------------------------------------------
start: setup
	@if [ -f "$(PID_FILE)" ] && kill -0 `cat $(PID_FILE)` 2>/dev/null; then \
		echo "⚠️  Service sudah berjalan (PID: `cat $(PID_FILE)`). Akses di: http://localhost:$(PORT)"; \
	else \
		echo "🚀 Menjalankan Web Dashboard Service pada port $(PORT)..."; \
		setsid $(PYTHON) main.py --serve --port $(PORT) --no-browser < /dev/null > $(LOG_FILE) 2>&1 & echo $$! > $(PID_FILE); \
		sleep 1; \
		if kill -0 `cat $(PID_FILE)` 2>/dev/null; then \
			echo "✅ Service BERHASIL dijalankan!"; \
			echo "   • PID: `cat $(PID_FILE)`"; \
			echo "   • URL: http://localhost:$(PORT)"; \
			echo "   • Log: $(LOG_FILE)"; \
		else \
			echo "❌ Gagal menjalankan service. Periksa log:"; \
			cat $(LOG_FILE); \
			rm -f $(PID_FILE); \
			exit 1; \
		fi; \
	fi

stop:
	@if [ -f "$(PID_FILE)" ]; then \
		PID=`cat $(PID_FILE)`; \
		if kill -0 $$PID 2>/dev/null; then \
			echo "🛑 Menghentikan service (PID: $$PID)..."; \
			kill $$PID 2>/dev/null || true; \
			sleep 1; \
			if kill -0 $$PID 2>/dev/null; then \
				kill -9 $$PID 2>/dev/null || true; \
			fi; \
			rm -f $(PID_FILE); \
			echo "✅ Service berhasil dihentikan."; \
		else \
			echo "⚠️  Proses dengan PID $$PID tidak ditemukan. Menghapus $(PID_FILE)..."; \
			rm -f $(PID_FILE); \
		fi; \
	else \
		echo "⚠️  File $(PID_FILE) tidak ditemukan. Mencari proses dashboard aktif..."; \
		PIDS=`pgrep -f "main.py --serve" || true`; \
		if [ -n "$$PIDS" ]; then \
			echo "🛑 Menghentikan proses (PID: $$PIDS)..."; \
			kill $$PIDS 2>/dev/null || true; \
			echo "✅ Proses dihentikan."; \
		else \
			echo "ℹ️  Tidak ada service yang sedang berjalan."; \
		fi; \
	fi

restart: stop start

status:
	@echo "📊 Status Web Dashboard Service:"
	@if [ -f "$(PID_FILE)" ] && kill -0 `cat $(PID_FILE)` 2>/dev/null; then \
		PID=`cat $(PID_FILE)`; \
		echo "  • Status  : 🟢 RUNNING"; \
		echo "  • PID     : $$PID"; \
		echo "  • URL     : http://localhost:$(PORT)"; \
		echo "  • Log File: $(LOG_FILE)"; \
		echo ""; \
		echo "📄 Log terakhir ($(LOG_FILE)):"; \
		tail -n 8 $(LOG_FILE) 2>/dev/null || true; \
	else \
		echo "  • Status  : 🔴 STOPPED"; \
		if [ -f "$(PID_FILE)" ]; then rm -f $(PID_FILE); fi; \
	fi

logs:
	@if [ -f "$(LOG_FILE)" ]; then \
		echo "📜 Menampilkan log $(LOG_FILE) (Ctrl+C untuk keluar)..."; \
		tail -f $(LOG_FILE); \
	else \
		echo "ℹ️  Log file $(LOG_FILE) belum ada. Jalankan 'make start' terlebih dahulu."; \
	fi

# ----------------------------------------------------------------------------
# Testing & Cleanup
# ----------------------------------------------------------------------------
test: setup
	@echo "🧪 Menjalankan unit tests..."
	@$(PYTHON) -m unittest discover tests

clean:
	@echo "🧹 Membersihkan temporary files & caches..."
	@rm -rf __pycache__ src/**/__pycache__ tests/__pycache__ .pytest_cache
	@rm -f $(PID_FILE)
	@echo "✅ Selesai."
