#!/usr/bin/env python3
"""
Comprehensive Rolling Day-by-Day Replay Backtest Runner.
Evaluates out-of-sample forward predictability across multiple assets, timeframes, and historical backward cutoff origins.
"""

import glob
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional
import numpy as np
import pandas as pd

# Add repo root to path
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from crypto_forecast_engine import run_replay_pipeline


def find_latest_file(pattern: str) -> Optional[str]:
    files = sorted(glob.glob(str(REPO_ROOT / pattern)))
    return files[-1] if files else None


def main():
    print("=" * 80)
    print("🚀 MEMULAI ROLLING DAY-BY-DAY REPLAY BACKTEST BENCHMARK")
    print("=" * 80)

    # Asset universe
    coins_1h = [
        "BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT",
        "DOGEUSDT", "ADAUSDT", "AVAXUSDT", "SUIUSDT", "LINKUSDT",
        "1000PEPEUSDT"
    ]

    # Windows on 1h (24h horizon per window)
    # Day -1 (back=24), Day -2 (back=48), ..., Day -14 (back=336)
    days_back_1h = [
        ("H-1 (Kemarin -> Hari Ini)", 24, 24),
        ("H-2 (2d lalu -> H-1)", 48, 24),
        ("H-3 (3d lalu -> H-2)", 72, 24),
        ("H-4 (4d lalu -> H-3)", 96, 24),
        ("H-5 (5d lalu -> H-4)", 120, 24),
        ("H-6 (6d lalu -> H-5)", 144, 24),
        ("H-7 (7d lalu -> H-6)", 168, 24),
        ("H-10 (10d lalu -> H-9)", 240, 24),
        ("H-14 (14d lalu -> H-13)", 336, 24),
    ]

    coins_4h = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT", "DOGEUSDT"]
    windows_4h = [
        ("4h Window 1 (24 jam)", 6, 6),
        ("4h Window 2 (48 jam)", 12, 12),
        ("4h Window 3 (3 hari)", 18, 18),
        ("4h Window 4 (4 hari)", 24, 24),
    ]

    coins_15m = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]
    windows_15m = [
        ("15m Window 1 (4 jam)", 16, 16),
        ("15m Window 2 (8 jam)", 32, 32),
        ("15m Window 3 (16 jam)", 64, 64),
        ("15m Window 4 (24 jam)", 96, 96),
    ]

    all_results: List[Dict[str, Any]] = []
    start_all = time.time()

    # 1. RUN 1-HOUR ROLLING DAY-BY-DAY
    print(f"\n[Fase 1/3] Menjalankan Pengujian Rolling Harian (1h Timeframe, 24h Horizon)...")
    for coin in coins_1h:
        file_path = find_latest_file(f"data/{coin}_1h_30d_*.json")
        if not file_path:
            print(f"  ⚠️ File untuk {coin} 1h tidak ditemukan, dilewati.")
            continue

        print(f"\n🪙 Menguji {coin} [1h]...")
        for label, back, horizon in days_back_1h:
            t0 = time.time()
            try:
                res = run_replay_pipeline(
                    source=file_path,
                    back_candles=back,
                    horizon_steps=horizon,
                    mc_simulations=1000,
                )
                s = res["summary"]
                dur = time.time() - t0

                match_str = "✅ SESUAI" if s["direction_match"] else "❌ BEDA"
                print(f"   • {label:24s} -> Cutoff: {s['cutoff_price']:>10.2f} | Akt: {s['final_actual_price']:>10.2f} ({s['actual_change_pct']:+6.2f}%) | Pred: {s['final_predicted_price']:>10.2f} ({s['predicted_change_pct']:+6.2f}%) | {match_str} | MAPE: {s['mape']:5.2f}% ({dur:.1f}s)")

                all_results.append({
                    "category": "1h_daily_rolling",
                    "symbol": coin,
                    "timeframe": "1h",
                    "window_label": label,
                    "back_candles": back,
                    "horizon_steps": horizon,
                    "cutoff_datetime": s["cutoff_datetime"],
                    "cutoff_price": s["cutoff_price"],
                    "final_actual_datetime": s["final_actual_datetime"],
                    "final_actual_price": s["final_actual_price"],
                    "final_predicted_price": s["final_predicted_price"],
                    "actual_change_pct": s["actual_change_pct"],
                    "predicted_change_pct": s["predicted_change_pct"],
                    "actual_direction": s["actual_direction"],
                    "predicted_direction": s["predicted_direction"],
                    "direction_match": s["direction_match"],
                    "rmse": s["rmse"],
                    "mae": s["mae"],
                    "mape": s["mape"],
                    "step_da": s["step_directional_accuracy"],
                    "pct_within_ci80": s["pct_within_ci80"],
                    "execution_time_sec": round(dur, 2),
                })
            except Exception as e:
                print(f"   • {label:24s} -> Error: {e}")

    # 2. RUN 4-HOUR SWING WINDOWS
    print(f"\n[Fase 2/3] Menjalankan Pengujian Swing (4h Timeframe)...")
    for coin in coins_4h:
        file_path = find_latest_file(f"data/{coin}_4h_30d_*.json")
        if not file_path:
            continue
        print(f"\n🪙 Menguji {coin} [4h]...")
        for label, back, horizon in windows_4h:
            t0 = time.time()
            try:
                res = run_replay_pipeline(
                    source=file_path,
                    back_candles=back,
                    horizon_steps=horizon,
                    mc_simulations=1000,
                )
                s = res["summary"]
                dur = time.time() - t0
                match_str = "✅ SESUAI" if s["direction_match"] else "❌ BEDA"
                print(f"   • {label:24s} -> Cutoff: {s['cutoff_price']:>10.2f} | Akt: {s['final_actual_price']:>10.2f} ({s['actual_change_pct']:+6.2f}%) | Pred: {s['final_predicted_price']:>10.2f} ({s['predicted_change_pct']:+6.2f}%) | {match_str} | MAPE: {s['mape']:5.2f}% ({dur:.1f}s)")
                all_results.append({
                    "category": "4h_swing",
                    "symbol": coin,
                    "timeframe": "4h",
                    "window_label": label,
                    "back_candles": back,
                    "horizon_steps": horizon,
                    "cutoff_datetime": s["cutoff_datetime"],
                    "cutoff_price": s["cutoff_price"],
                    "final_actual_datetime": s["final_actual_datetime"],
                    "final_actual_price": s["final_actual_price"],
                    "final_predicted_price": s["final_predicted_price"],
                    "actual_change_pct": s["actual_change_pct"],
                    "predicted_change_pct": s["predicted_change_pct"],
                    "actual_direction": s["actual_direction"],
                    "predicted_direction": s["predicted_direction"],
                    "direction_match": s["direction_match"],
                    "rmse": s["rmse"],
                    "mae": s["mae"],
                    "mape": s["mape"],
                    "step_da": s["step_directional_accuracy"],
                    "pct_within_ci80": s["pct_within_ci80"],
                    "execution_time_sec": round(dur, 2),
                })
            except Exception as e:
                print(f"   • {label:24s} -> Error: {e}")

    # 3. RUN 15-MINUTE INTRADAY SCALPS
    print(f"\n[Fase 3/3] Menjalankan Pengujian Intraday (15m Timeframe)...")
    for coin in coins_15m:
        file_path = find_latest_file(f"data/{coin}_15m_30d_*.json")
        if not file_path:
            continue
        print(f"\n🪙 Menguji {coin} [15m]...")
        for label, back, horizon in windows_15m:
            t0 = time.time()
            try:
                res = run_replay_pipeline(
                    source=file_path,
                    back_candles=back,
                    horizon_steps=horizon,
                    mc_simulations=1000,
                )
                s = res["summary"]
                dur = time.time() - t0
                match_str = "✅ SESUAI" if s["direction_match"] else "❌ BEDA"
                print(f"   • {label:24s} -> Cutoff: {s['cutoff_price']:>10.2f} | Akt: {s['final_actual_price']:>10.2f} ({s['actual_change_pct']:+6.2f}%) | Pred: {s['final_predicted_price']:>10.2f} ({s['predicted_change_pct']:+6.2f}%) | {match_str} | MAPE: {s['mape']:5.2f}% ({dur:.1f}s)")
                all_results.append({
                    "category": "15m_intraday",
                    "symbol": coin,
                    "timeframe": "15m",
                    "window_label": label,
                    "back_candles": back,
                    "horizon_steps": horizon,
                    "cutoff_datetime": s["cutoff_datetime"],
                    "cutoff_price": s["cutoff_price"],
                    "final_actual_datetime": s["final_actual_datetime"],
                    "final_actual_price": s["final_actual_price"],
                    "final_predicted_price": s["final_predicted_price"],
                    "actual_change_pct": s["actual_change_pct"],
                    "predicted_change_pct": s["predicted_change_pct"],
                    "actual_direction": s["actual_direction"],
                    "predicted_direction": s["predicted_direction"],
                    "direction_match": s["direction_match"],
                    "rmse": s["rmse"],
                    "mae": s["mae"],
                    "mape": s["mape"],
                    "step_da": s["step_directional_accuracy"],
                    "pct_within_ci80": s["pct_within_ci80"],
                    "execution_time_sec": round(dur, 2),
                })
            except Exception as e:
                print(f"   • {label:24s} -> Error: {e}")

    total_time = time.time() - start_all
    df_all = pd.DataFrame(all_results)

    # Save to CSV and JSON
    out_csv = REPO_ROOT / "data" / "replay_benchmark_results.csv"
    out_json = REPO_ROOT / "data" / "replay_benchmark_results.json"
    out_csv_date = REPO_ROOT / "data" / "replay_benchmark_results_20261104.csv"
    out_json_date = REPO_ROOT / "data" / "replay_benchmark_results_20261104.json"
    df_all.to_csv(out_csv, index=False)
    df_all.to_csv(out_csv_date, index=False)
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(all_results, f, indent=2)
    with open(out_json_date, "w", encoding="utf-8") as f:
        json.dump(all_results, f, indent=2)

    print("\n" + "=" * 80)
    print(f"✅ BENCHMARK SELESAI ({total_time:.1f} detik)")
    print(f"• Total Pengujian Sukses : {len(df_all)} pengujian replay")
    print(f"• Output CSV             : {out_csv}")
    print(f"• Output JSON            : {out_json}")

    # Summary statistics
    win_rate = df_all["direction_match"].mean() * 100.0
    avg_mape = df_all["mape"].mean()
    avg_step_da = df_all["step_da"].mean()
    avg_ci80 = df_all["pct_within_ci80"].mean()

    print("\n📈 RINGKASAN AGREGAT GLOBAL:")
    print(f"  • Overall Directional Match (Win Rate) : {win_rate:.2f}%")
    print(f"  • Rata-rata MAPE Error                 : {avg_mape:.2f}%")
    print(f"  • Rata-rata Step Directional Accuracy  : {avg_step_da:.2f}%")
    print(f"  • Rata-rata Realitas dalam CI 80%      : {avg_ci80:.2f}%")
    print("=" * 80)


if __name__ == "__main__":
    main()
