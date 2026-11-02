#!/usr/bin/env python3
"""
FastAPI Web Server for Crypto Forecast Engine.
Provides REST API endpoints and serves the modern interactive web application.
"""

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, File, Form, HTTPException, Query, UploadFile, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import numpy as np

from crypto_forecast_engine import (
    CryptoForecastEngine,
    ForecastConfig,
    run_forecast_pipeline,
)
from src.collector.binance import BinanceCollector, normalize_symbol

logger = logging.getLogger(__name__)

# Base directories
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
WEB_DIR = BASE_DIR / "web"

app = FastAPI(
    title="Antigravity Crypto Forecast Engine API",
    description="Multi-Method Quantitative Forecasting Engine for Crypto Market Data",
    version="2.0.0",
)

# Enable CORS for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class LiveForecastRequest(BaseModel):
    symbol: str = "ETHUSDT"
    timeframe: str = "15m"
    days: int = 1
    horizon_steps: int = 48
    mc_simulations: int = 10000
    save_dataset: bool = True


class SimulateBarriersRequest(BaseModel):
    current_price: float
    ensemble_path: List[float]
    ci_80_upper: List[float]
    upside_barriers: List[float]
    downside_barriers: List[float]
    step_minutes: int = 15
    mc_simulations: int = 10000
    student_df: int = 6


@app.get("/api/health")
def health_check():
    return {
        "status": "healthy",
        "engine": "CryptoForecastEngine",
        "version": "2.0.0",
        "data_dir": str(DATA_DIR),
    }


@app.get("/api/presets")
def get_presets():
    """Lists available pre-loaded JSON market datasets."""
    presets = []
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    for p in sorted(DATA_DIR.glob("*.json")):
        try:
            with open(p, "r", encoding="utf-8") as f:
                data = json.load(f)
            meta = data.get("metadata", {})
            candles = data.get("data", [])
            last_price = None
            if candles:
                last_price = float(candles[-1].get("close", 0.0))
            elif "summary_stats" in meta:
                last_price = meta["summary_stats"].get("latest_price")

            presets.append({
                "filename": p.name,
                "symbol": meta.get("symbol", p.stem.split("_")[0]),
                "timeframe": meta.get("timeframe", "15m"),
                "period_days": meta.get("period_days", 1),
                "total_candles": len(candles) or meta.get("total_candles", 0),
                "latest_price": last_price,
                "start_time": meta.get("start_time"),
                "end_time": meta.get("end_time"),
                "size_kb": round(p.stat().st_size / 1024, 1),
            })
        except Exception as e:
            logger.warning(f"Failed to read preset {p.name}: {e}")
    return presets


@app.get("/api/forecast/preset/{filename}")
def forecast_preset(
    filename: str,
    horizon: int = Query(48, ge=4, le=288),
    mc_sims: int = Query(10000, ge=1000, le=50000),
):
    """Runs full quantitative forecast on a preset dataset in data/."""
    file_path = DATA_DIR / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail=f"File '{filename}' not found in data directory.")

    try:
        results = run_forecast_pipeline(
            source=str(file_path),
            horizon_steps=horizon,
            mc_simulations=mc_sims,
        )
        return results
    except Exception as e:
        logger.error(f"Forecast failed for preset {filename}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Forecast calculation failed: {str(e)}")


@app.post("/api/forecast/upload")
async def forecast_upload(
    file: UploadFile = File(...),
    horizon: int = Form(48),
    mc_sims: int = Form(10000),
):
    """Accepts uploaded JSON candlestick dataset and runs forecast."""
    try:
        content = await file.read()
        raw = json.loads(content.decode("utf-8"))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid JSON file: {str(e)}")

    try:
        results = run_forecast_pipeline(
            source=raw,
            horizon_steps=horizon,
            mc_simulations=mc_sims,
        )
        return results
    except Exception as e:
        logger.error(f"Forecast failed for uploaded file: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Forecast pipeline error: {str(e)}")


@app.post("/api/forecast/live")
def forecast_live(req: LiveForecastRequest):
    """Fetches live market data from Binance Futures, saves with timestamp, and immediately generates forecasts."""
    try:
        norm_sym = normalize_symbol(req.symbol)
        collector = BinanceCollector(use_doh=True)
        dataset = collector.collect(
            symbol=norm_sym,
            timeframe=req.timeframe,
            days=req.days,
        )

        now_dt = datetime.now()
        now_ts = now_dt.strftime("%Y%m%d_%H%M%S")
        filename = f"{norm_sym}_{req.timeframe}_{req.days}d_{now_ts}.json"
        dataset["metadata"]["downloaded_at"] = now_dt.strftime("%Y-%m-%d %H:%M:%S")

        if req.save_dataset:
            DATA_DIR.mkdir(parents=True, exist_ok=True)
            out_file = DATA_DIR / filename
            collector.save_json(dataset, str(out_file))

        results = run_forecast_pipeline(
            source=dataset,
            horizon_steps=req.horizon_steps,
            mc_simulations=req.mc_simulations,
        )
        results["raw_dataset"] = dataset
        results["dataset_filename"] = filename
        results["download_timestamp"] = now_ts
        return results
    except Exception as e:
        logger.error(f"Live forecast failed for {req.symbol}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Live market data fetch or forecast failed: {str(e)}")


@app.get("/api/binance/download")
def download_binance_data(
    symbol: str = Query("ETHUSDT", description="Simbol kripto (contoh: ETHUSDT, BTCUSDT)"),
    timeframe: str = Query("15m", description="Interval candle (contoh: 15m, 1h)"),
    days: int = Query(1, ge=1, le=90, description="Jumlah hari riwayat"),
    save_server: bool = Query(True, description="Simpan salinan ke folder data/ di server"),
):
    """Tarik data Binance Futures dan unduh sebagai file JSON ber-timestamp ke komputer pengguna."""
    try:
        norm_sym = normalize_symbol(symbol)
        collector = BinanceCollector(use_doh=True)
        dataset = collector.collect(
            symbol=norm_sym,
            timeframe=timeframe,
            days=days,
        )
        now_dt = datetime.now()
        now_ts = now_dt.strftime("%Y%m%d_%H%M%S")
        filename = f"{norm_sym}_{timeframe}_{days}d_{now_ts}.json"
        dataset["metadata"]["downloaded_at"] = now_dt.strftime("%Y-%m-%d %H:%M:%S")

        if save_server:
            DATA_DIR.mkdir(parents=True, exist_ok=True)
            out_file = DATA_DIR / filename
            collector.save_json(dataset, str(out_file))

        json_bytes = json.dumps(dataset, indent=2).encode("utf-8")
        return Response(
            content=json_bytes,
            media_type="application/json",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
                "Access-Control-Expose-Headers": "Content-Disposition, X-Dataset-Filename",
                "X-Dataset-Filename": filename,
            },
        )
    except Exception as e:
        logger.error(f"Binance download failed for {symbol}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Gagal mengunduh data Binance: {str(e)}")


@app.post("/api/barriers/simulate")
def simulate_barriers(req: SimulateBarriersRequest):
    """Fast Monte Carlo first-passage touch probability recalculation for custom user barriers."""
    try:
        p0 = req.current_price
        ens_path = np.array(req.ensemble_path)
        ci80_up = np.array(req.ci_80_upper)
        H = len(ens_path)

        log_drifts = np.diff(np.log(np.concatenate([[p0], ens_path])))
        cum_std = (ci80_up / ens_path - 1.0) / 1.2816
        step_var = np.diff(np.concatenate([[0.0], cum_std ** 2]))
        step_std = np.sqrt(np.maximum(step_var, (0.0012) ** 2))

        rng = np.random.default_rng(42)
        df_t = req.student_df
        Z = rng.standard_t(df=df_t, size=(req.mc_simulations, H)) * np.sqrt((df_t - 2.0) / df_t)
        sim_log_rets = log_drifts[None, :] + step_std[None, :] * Z
        sim_paths = p0 * np.exp(np.cumsum(sim_log_rets, axis=1))

        h_24 = min(int(1440 / req.step_minutes), H)

        probs = {"upside": {}, "downside": {}}
        for b in req.upside_barriers:
            pct_dist = ((b - p0) / p0) * 100.0
            probs["upside"][str(b)] = {
                "barrier_price": float(b),
                "distance_pct": round(pct_dist, 2),
                "touch_24h_pct": round(float(np.mean(np.max(sim_paths[:, :h_24], axis=1) >= b) * 100.0), 2),
                "touch_horizon_pct": round(float(np.mean(np.max(sim_paths[:, :H], axis=1) >= b) * 100.0), 2),
            }
        for b in req.downside_barriers:
            pct_dist = ((b - p0) / p0) * 100.0
            probs["downside"][str(b)] = {
                "barrier_price": float(b),
                "distance_pct": round(pct_dist, 2),
                "touch_24h_pct": round(float(np.mean(np.min(sim_paths[:, :h_24], axis=1) <= b) * 100.0), 2),
                "touch_horizon_pct": round(float(np.mean(np.min(sim_paths[:, :H], axis=1) <= b) * 100.0), 2),
            }
        return probs
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Barrier simulation error: {str(e)}")


# Serve static web files
if WEB_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(WEB_DIR)), name="static")


@app.get("/", response_class=HTMLResponse)
def index():
    index_file = WEB_DIR / "index.html"
    if index_file.exists():
        with open(index_file, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    return HTMLResponse("<h1>Web interface not found. Please create web/index.html</h1>", status_code=404)


def run_server(host: str = "127.0.0.1", port: int = 8000, reload: bool = False):
    """Starts the Uvicorn web server."""
    import uvicorn
    print(f"\n🚀 Memulai Antigravity Crypto Predictor Web Server...")
    print(f"📡 Akses antarmuka web di: http://{host}:{port}")
    uvicorn.run("src.web_server:app", host=host, port=port, reload=reload)


if __name__ == "__main__":
    run_server()
