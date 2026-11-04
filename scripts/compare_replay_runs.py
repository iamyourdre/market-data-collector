#!/usr/bin/env python3
"""
Comparison script between two Replay Backtest benchmark runs (e.g. 2026-11-02 vs 2026-11-04).
Computes deltas for Win Rate, MAPE, Step DA, CI 80%, per-timeframe, and per-asset performance.
"""

import argparse
import json
from pathlib import Path
import pandas as pd
import numpy as np

REPO_ROOT = Path(__file__).resolve().parent.parent


def compare_benchmarks(base_csv: Path, current_csv: Path):
    if not base_csv.exists():
        raise FileNotFoundError(f"Base benchmark file {base_csv} tidak ditemukan.")
    if not current_csv.exists():
        raise FileNotFoundError(f"Current benchmark file {current_csv} tidak ditemukan.")

    df_base = pd.read_csv(base_csv)
    df_curr = pd.read_csv(current_csv)

    # 1. Global Metrics
    base_n = len(df_base)
    curr_n = len(df_curr)

    base_win = df_base["direction_match"].mean() * 100.0
    curr_win = df_curr["direction_match"].mean() * 100.0
    delta_win = curr_win - base_win

    base_mape = df_base["mape"].mean()
    curr_mape = df_curr["mape"].mean()
    delta_mape = curr_mape - base_mape

    base_step = df_base["step_da"].mean()
    curr_step = df_curr["step_da"].mean()
    delta_step = curr_step - base_step

    base_ci = df_base["pct_within_ci80"].mean()
    curr_ci = df_curr["pct_within_ci80"].mean()
    delta_ci = curr_ci - base_ci

    # 2. Category / Timeframe breakdown
    categories = sorted(list(set(df_base["category"]).union(set(df_curr["category"]))))
    cat_summary = []
    for cat in categories:
        b_sub = df_base[df_base["category"] == cat]
        c_sub = df_curr[df_curr["category"] == cat]
        
        b_w = b_sub["direction_match"].mean() * 100.0 if len(b_sub) > 0 else 0.0
        c_w = c_sub["direction_match"].mean() * 100.0 if len(c_sub) > 0 else 0.0
        b_m = b_sub["mape"].mean() if len(b_sub) > 0 else 0.0
        c_m = c_sub["mape"].mean() if len(c_sub) > 0 else 0.0
        b_s = b_sub["step_da"].mean() if len(b_sub) > 0 else 0.0
        c_s = c_sub["step_da"].mean() if len(c_sub) > 0 else 0.0
        
        cat_summary.append({
            "category": cat,
            "base_count": len(b_sub),
            "curr_count": len(c_sub),
            "base_win_rate": round(b_w, 2),
            "curr_win_rate": round(c_w, 2),
            "delta_win_rate": round(c_w - b_w, 2),
            "base_mape": round(b_m, 2),
            "curr_mape": round(c_m, 2),
            "delta_mape": round(c_m - b_m, 2),
            "base_step_da": round(b_s, 2),
            "curr_step_da": round(c_s, 2),
            "delta_step_da": round(c_s - b_s, 2),
        })

    # 3. 1h Daily Rolling Coin-by-Coin comparison
    coins = sorted(list(set(df_base[df_base["timeframe"] == "1h"]["symbol"]).intersection(
        set(df_curr[df_curr["timeframe"] == "1h"]["symbol"])
    )))

    coin_summary = []
    for coin in coins:
        b_c = df_base[(df_base["timeframe"] == "1h") & (df_base["symbol"] == coin)]
        c_c = df_curr[(df_curr["timeframe"] == "1h") & (df_curr["symbol"] == coin)]

        b_win = b_c["direction_match"].mean() * 100.0 if len(b_c) > 0 else 0.0
        c_win = c_c["direction_match"].mean() * 100.0 if len(c_c) > 0 else 0.0
        b_m = b_c["mape"].mean() if len(b_c) > 0 else 0.0
        c_m = c_c["mape"].mean() if len(c_c) > 0 else 0.0
        b_s = b_c["step_da"].mean() if len(b_c) > 0 else 0.0
        c_s = c_c["step_da"].mean() if len(c_c) > 0 else 0.0

        coin_summary.append({
            "symbol": coin,
            "base_win_rate": round(b_win, 2),
            "curr_win_rate": round(c_win, 2),
            "delta_win_rate": round(c_win - b_win, 2),
            "base_mape": round(b_m, 2),
            "curr_mape": round(c_m, 2),
            "delta_mape": round(c_m - b_m, 2),
            "base_step_da": round(b_s, 2),
            "curr_step_da": round(c_s, 2),
            "delta_step_da": round(c_s - b_s, 2),
        })

    # Sort coins by current win rate desc, then current mape asc
    coin_summary = sorted(coin_summary, key=lambda x: (-x["curr_win_rate"], x["curr_mape"]))

    # 4. H-1 (Kemarin -> Hari Ini) Specific Comparison across coins
    h1_base = df_base[df_base["window_label"].str.contains("H-1", na=False)]
    h1_curr = df_curr[df_curr["window_label"].str.contains("H-1", na=False)]

    h1_summary = []
    for coin in coins:
        b_row = h1_base[h1_base["symbol"] == coin]
        c_row = h1_curr[h1_curr["symbol"] == coin]
        if not b_row.empty and not c_row.empty:
            b_r = b_row.iloc[0]
            c_r = c_row.iloc[0]
            h1_summary.append({
                "symbol": coin,
                "base_match": bool(b_r["direction_match"]),
                "curr_match": bool(c_r["direction_match"]),
                "base_actual_chg": round(float(b_r["actual_change_pct"]), 2),
                "base_pred_chg": round(float(b_r["predicted_change_pct"]), 2),
                "base_mape": round(float(b_r["mape"]), 2),
                "curr_actual_chg": round(float(c_r["actual_change_pct"]), 2),
                "curr_pred_chg": round(float(c_r["predicted_change_pct"]), 2),
                "curr_mape": round(float(c_r["mape"]), 2),
            })

    report = {
        "metadata": {
            "base_file": str(base_csv.name),
            "current_file": str(current_csv.name),
            "base_total_tests": base_n,
            "current_total_tests": curr_n,
        },
        "global_comparison": {
            "base_win_rate": round(base_win, 2),
            "curr_win_rate": round(curr_win, 2),
            "delta_win_rate": round(delta_win, 2),
            "base_mape": round(base_mape, 2),
            "curr_mape": round(curr_mape, 2),
            "delta_mape": round(delta_mape, 2),
            "base_step_da": round(base_step, 2),
            "curr_step_da": round(curr_step, 2),
            "delta_step_da": round(delta_step, 2),
            "base_ci80": round(base_ci, 2),
            "curr_ci80": round(curr_ci, 2),
            "delta_ci80": round(delta_ci, 2),
        },
        "timeframe_comparison": cat_summary,
        "coin_comparison_1h": coin_summary,
        "h1_comparison": h1_summary,
    }

    return report


def main():
    parser = argparse.ArgumentParser(description="Compare two Replay Backtest benchmark runs")
    parser.add_argument("--base", type=str, default=str(REPO_ROOT / "data" / "replay_benchmark_results_20261102.csv"))
    parser.add_argument("--current", type=str, default=str(REPO_ROOT / "data" / "replay_benchmark_results.csv"))
    parser.add_argument("--out-json", type=str, default=str(REPO_ROOT / "data" / "replay_benchmark_comparison.json"))
    args = parser.parse_args()

    base_path = Path(args.base)
    curr_path = Path(args.current)

    report = compare_benchmarks(base_path, curr_path)

    # Save JSON
    out_json_path = Path(args.out_json)
    with open(out_json_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    g = report["global_comparison"]
    print("=" * 80)
    print("📊 PERBANDINGAN HASIL REPLAY BACKTEST (BENCHMARK 02 NOV VS 04 NOV)")
    print("=" * 80)
    print(f"Metrik Global                  | 02 Nov 2026 | 04 Nov 2026 | Delta (Perubahan)")
    print("─────────────────────────────────────────────────────────────────────────────")
    sign_win = "+" if g["delta_win_rate"] >= 0 else ""
    sign_mape = "+" if g["delta_mape"] >= 0 else ""
    sign_step = "+" if g["delta_step_da"] >= 0 else ""
    sign_ci = "+" if g["delta_ci80"] >= 0 else ""

    print(f"Overall Directional Win Rate   | {g['base_win_rate']:>10.2f}% | {g['curr_win_rate']:>10.2f}% | {sign_win}{g['delta_win_rate']:.2f}%")
    print(f"Average MAPE Error             | {g['base_mape']:>10.2f}% | {g['curr_mape']:>10.2f}% | {sign_mape}{g['delta_mape']:.2f}%")
    print(f"Step Directional Accuracy (DA) | {g['base_step_da']:>10.2f}% | {g['curr_step_da']:>10.2f}% | {sign_step}{g['delta_step_da']:.2f}%")
    print(f"GARCH Realized in 80% CI       | {g['base_ci80']:>10.2f}% | {g['curr_ci80']:>10.2f}% | {sign_ci}{g['delta_ci80']:.2f}%")
    print("=" * 80)

    print("\n⏱️ PERBANDINGAN BERDASARKAN TIMEFRAME:")
    print("─────────────────────────────────────────────────────────────────────────────")
    print(f"{'Kategori Timeframe':<22} | {'Win Rate (02 Nov)':<17} | {'Win Rate (04 Nov)':<17} | {'Delta Win':<10}")
    print("─────────────────────────────────────────────────────────────────────────────")
    for c in report["timeframe_comparison"]:
        s_w = "+" if c["delta_win_rate"] >= 0 else ""
        print(f"{c['category']:<22} | {c['base_win_rate']:>15.2f}% | {c['curr_win_rate']:>15.2f}% | {s_w}{c['delta_win_rate']:.2f}%")
    print("=" * 80)

    print("\n🪙 PERBANDINGAN PER KOIN (1h Daily Rolling 24h Horizon):")
    print("─────────────────────────────────────────────────────────────────────────────")
    print(f"{'Simbol':<12} | {'Win (Nov 02)':<12} | {'Win (Nov 04)':<12} | {'Delta Win':<10} | {'MAPE (Nov 02)':<13} | {'MAPE (Nov 04)':<13}")
    print("─────────────────────────────────────────────────────────────────────────────")
    for coin in report["coin_comparison_1h"]:
        s_w = "+" if coin["delta_win_rate"] >= 0 else ""
        print(f"{coin['symbol']:<12} | {coin['base_win_rate']:>10.2f}% | {coin['curr_win_rate']:>10.2f}% | {s_w}{coin['delta_win_rate']:>8.2f}% | {coin['base_mape']:>11.2f}% | {coin['curr_mape']:>11.2f}%")
    print("=" * 80)
    print(f"📁 Hasil perbandingan tersimpan di: {out_json_path}")


if __name__ == "__main__":
    main()

