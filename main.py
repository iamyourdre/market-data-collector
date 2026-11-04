#!/usr/bin/env python3
"""
Crypto Predictor System - Main Entry Point.
Provides unified CLI for data collection, quantitative forecasting, and web dashboard.
"""

import argparse
import sys

from src.collector import setup_collector_cli_args, run_collector_cli


def setup_forecast_cli_args(parser: argparse.ArgumentParser):
    parser.add_argument(
        "--input",
        "-i",
        type=str,
        default="data/ETHUSDT_15m_1d.json",
        help="Path file dataset JSON (contoh: data/ETHUSDT_15m_1d.json)",
    )
    parser.add_argument(
        "--horizon",
        "-H",
        type=int,
        default=48,
        help="Horizon peramalan dalam langkah lilin (default: 48)",
    )
    parser.add_argument(
        "--mc-sims",
        type=int,
        default=10000,
        help="Jumlah simulasi Monte Carlo Student-t (default: 10000)",
    )
    parser.add_argument(
        "--out-csv",
        type=str,
        default="forecast_trajectories.csv",
        help="Path file output CSV trajectory",
    )
    parser.add_argument(
        "--out-json",
        type=str,
        default="forecast_summary.json",
        help="Path file output JSON summary",
    )


def setup_web_cli_args(parser: argparse.ArgumentParser):
    parser.add_argument(
        "--host",
        type=str,
        default="127.0.0.1",
        help="Host listener web server (default: 127.0.0.1)",
    )
    parser.add_argument(
        "--port",
        "-p",
        type=int,
        default=8000,
        help="Port listener web server (default: 8000)",
    )
    parser.add_argument(
        "--reload",
        action="store_true",
        help="Aktifkan auto-reload server FastAPI",
    )


def setup_replay_cli_args(parser: argparse.ArgumentParser):
    parser.add_argument(
        "--input",
        "-i",
        type=str,
        default="data/ETHUSDT_15m_1d.json",
        help="Path file dataset JSON (contoh: data/BTCUSDT_1h_30d_...json)",
    )
    parser.add_argument(
        "--back",
        "-b",
        type=int,
        default=24,
        help="Jumlah lilin (candles) mundur ke masa lalu untuk titik cutoff (default: 24)",
    )
    parser.add_argument(
        "--horizon",
        "-H",
        type=int,
        default=None,
        help="Horizon langkah ramalan dari titik cutoff (default: sama dengan nilai --back)",
    )
    parser.add_argument(
        "--mc-sims",
        type=int,
        default=5000,
        help="Jumlah simulasi Monte Carlo Student-t (default: 5000)",
    )
    parser.add_argument(
        "--out-json",
        type=str,
        default=None,
        help="Path file output JSON summary (opsional)",
    )


def main():
    parser = argparse.ArgumentParser(
        description="Crypto Predictor System - Platform Analisis & Prediksi Pasar Kripto Kuantitatif",
        epilog="Gunakan 'python main.py <subcommand> --help' untuk bantuan sub-fitur tertentu.",
    )
    subparsers = parser.add_subparsers(
        title="Sub-fitur yang tersedia",
        dest="subcommand",
        help="Pilih sub-fitur untuk dijalankan",
    )

    # Sub-fitur 1: Data Collector
    collect_parser = subparsers.add_parser(
        "collect",
        help="Ambil data pasar historis Binance Futures ke format JSON (OHLCV, Funding Rate, Open Interest)",
    )
    setup_collector_cli_args(collect_parser)

    # Sub-fitur 2: Forecast Engine
    forecast_parser = subparsers.add_parser(
        "forecast",
        help="Jalankan peramalan kuantitatif multi-metode (Holt, Fourier, Kalman, ARX-Ridge, kNN, GARCH)",
    )
    setup_forecast_cli_args(forecast_parser)

    # Sub-fitur 3: Web Dashboard Server
    web_parser = subparsers.add_parser(
        "web",
        help="Jalankan antarmuka dashboard web interaktif (TradingView chart, probabilitas barrier, live fetch)",
    )
    setup_web_cli_args(web_parser)

    # Sub-fitur 4: Historical Cutoff Replay Backtest
    replay_parser = subparsers.add_parser(
        "replay",
        help="Uji akurasi waktu mundur: potong data di masa lalu untuk meramal lilin setelahnya hingga hari ini",
    )
    setup_replay_cli_args(replay_parser)

    args = parser.parse_args()

    if not args.subcommand:
        parser.print_help()
        sys.exit(0)

    try:
        if args.subcommand == "collect":
            run_collector_cli(args)
        elif args.subcommand == "forecast":
            from crypto_forecast_engine import run_forecast_pipeline
            import json
            import pandas as pd

            print(f"🚀 Memulai Quantitative Forecast Engine...")
            print(f"📂 Dataset Input: {args.input}")
            print(f"⏱️  Horizon Steps: {args.horizon} | Monte Carlo: {args.mc_sims:,} paths")

            res = run_forecast_pipeline(
                source=args.input,
                horizon_steps=args.horizon,
                mc_simulations=args.mc_sims,
            )

            meta = res["metadata"]
            sum_data = res["summary"]
            metrics = res["backtest_metrics"]
            weights = res["ensemble_weights"]
            spot = res.get("spot_order_recommendation", {})

            print(f"   -> Terbaca {meta.get('total_candles')} candles ({meta.get('symbol')} {meta.get('timeframe')})")
            print(f"   -> Harga Penutupan Terakhir: ${sum_data['last_close']:,.4f}")
            print(f"   -> Rezim Pasar Terdeteksi  : {sum_data.get('market_regime', 'UNKNOWN')}")

            print("\n📊 Bobot Ensemble & Akurasi Walk-Forward:")
            for m_name, w in weights.items():
                m_met = metrics.get(m_name, {})
                print(f"   • {m_name:20s}: {w * 100:5.2f}% | Path RMSE: ${m_met.get('RMSE_Path', 0.0):,.4f} | DA: {m_met.get('DA_Avg', 0.0):.2f}%")
            ens_m = metrics.get("M6_Best_Ensemble", {})
            print(f"   🎯 Ensemble Terbaik -> Path RMSE: ${ens_m.get('RMSE_Path', 0.0):,.4f} | Avg DA: {ens_m.get('DA_Avg', 0.0):.2f}%")
            print(f"   🔮 Target Horizon ({sum_data.get('horizon_hours')}h) -> ${sum_data.get('horizon_target'):,.4f} ({sum_data.get('expected_return_pct'):+.2f}%) [{sum_data.get('direction')}]")

            if spot:
                print("\n" + "=" * 80)
                print(f"🎯 REKOMENDASI SETINGAN OPEN ORDER SPOT ({meta.get('symbol', 'UNKNOWN')})")
                print("=" * 80)
                print(f"• Keputusan / Vonis     : {spot['action_badge']} ({spot['verdict']})")
                print(f"• Profil Risiko Pasar   : {spot['risk_level']} | Rezim: {sum_data.get('market_regime')}")
                print(f"• Saran Alokasi Modal   : {spot['recommended_portfolio_allocation']}")
                print(f"• Rasio Risk / Reward   : {spot['risk_reward_ratio']:.2f} : 1 (Ekspektasi: +{spot['expected_blended_gain_pct']:.2f}% | Risiko SL: {spot['stop_loss_risk_pct']:.2f}%)")
                print(f"• Breakout Entry Level  : ${spot['breakout_entry_trigger']:,.4f} (Stop Limit Buy jika momentum breakout)")
                print("-" * 80)
                print("📥 LADDER 1: STRATEGI PEMBELIAN DCA (STAGGERED LIMIT BIDS)")
                print(f"{'Tier Order':35s} | {'Harga Limit':14s} | {'Jarak Spot':11s} | {'Bobot Modal':11s}")
                print("-" * 80)
                for e in spot.get("entry_ladder", []):
                    print(f"{e['tier']:35s} | ${e['price']:12,.4f} | {e['offset_pct']:+9.2f}% | {e['weight_pct']:8d}%")
                print("-" * 80)
                print(f"⭐️ Rata-rata Entry (Blended Entry) : ${spot['blended_entry_price']:,.4f} (Diskon {abs(spot['blended_entry_discount_pct']):.2f}% dari spot)")
                print("-" * 80)
                print("💰 LADDER 2: TARGET TAKE PROFIT BERTAHAP (SCALED SELLING)")
                print(f"{'Target Take Profit':35s} | {'Harga Jual':14s} | {'Potensi Cuan':12s} | {'Porsi Jual':11s}")
                print("-" * 80)
                for t in spot.get("take_profit_ladder", []):
                    print(f"{t['tier']:35s} | ${t['price']:12,.4f} | {t['gain_pct']:+10.2f}% | {t['close_qty_pct']:8d}%")
                print("-" * 80)
                print(f"⭐️ Rata-rata Take Profit (Blended TP): ${spot['blended_take_profit_price']:,.4f} (Rata-rata cuan +{spot['expected_blended_gain_pct']:.2f}%)")
                print("-" * 80)
                print("🛡️ PROTEKSI INVALIDASI & STOP LOSS")
                print(f"• Level Invalidation Stop Loss       : ${spot['stop_loss_price']:,.4f} ({spot['stop_loss_risk_pct']:.2f}% dari Blended Entry)")
                print(f"• Rasional Invalidation              : {spot['invalidation_rationale']}")
                print("=" * 80)

            # Export files
            df_fc = pd.DataFrame(res["forecast_data"])
            df_fc.to_csv(args.out_csv, index=False)
            with open(args.out_json, "w", encoding="utf-8") as f:
                json.dump(res, f, indent=2)

            print(f"\n✅ Selesai! Trajectory disimpan ke: {args.out_csv}")
            print(f"✅ Ringkasan lengkap disimpan ke: {args.out_json}")

        elif args.subcommand == "replay":
            from crypto_forecast_engine import run_replay_pipeline
            import json

            print(f"⏱️  Menjalankan Replay Backtest (Waktu Mundur)...")
            print(f"📂 Dataset Input : {args.input}")
            print(f"⏪ Waktu Mundur  : {args.back} candles")

            res = run_replay_pipeline(
                source=args.input,
                back_candles=args.back,
                horizon_steps=args.horizon,
                mc_simulations=args.mc_sims,
            )

            s = res["summary"]
            print("\n" + "=" * 75)
            print(f"📊 HASIL UJI WAKTU MUNDUR: {s['symbol']} ({s['timeframe']}) — Mundur {s['back_candles']} Lilin")
            print("=" * 75)
            print(f"• Titik Cutoff (Waktu Lalu)   : {s['cutoff_datetime']} | Harga: ${s['cutoff_price']:,.4f}")
            print(f"• Titik Akhir (Waktu Realitas): {s['final_actual_datetime']}")
            print(f"• Harga Aktual Realitas       : ${s['final_actual_price']:,.4f} ({s['actual_change_pct']:+.2f}%) [{s['actual_direction']}]")
            print(f"• Harga Prediksi Model        : ${s['final_predicted_price']:,.4f} ({s['predicted_change_pct']:+.2f}%) [{s['predicted_direction']}]")
            match_badge = "✅ SESUAI (Arah Pasar Tertebak Benar)" if s['direction_match'] else "❌ TIDAK SESUAI (Arah Pasar Berbeda)"
            print(f"• Keselarasan Arah Akhir      : {match_badge}")
            print("-" * 75)
            print(f"• Metrik Error Deviasi:")
            print(f"  - RMSE (Root Mean Sq Error) : ${s['rmse']:,.4f}")
            print(f"  - MAE (Mean Absolute Error) : ${s['mae']:,.4f}")
            print(f"  - MAPE (Rata-rata % Error)  : {s['mape']:.2f}%")
            print(f"  - Max Error Nominal         : ${s['max_error_usd']:,.4f}")
            print(f"  - Step Directional Accuracy : {s['step_directional_accuracy']:.1f}%")
            print(f"  - Realitas Dalam Corong 80% : {s['pct_within_ci80']:.1f}% lilin")
            print("=" * 75)

            steps = res["comparison_steps"]
            print(f"\n📋 Cuplikan Proyeksi vs Realitas ({len(steps)} Langkah Lilin):")
            print(f"{'Step':4s} | {'Waktu':20s} | {'Aktual Close':14s} | {'Pred Close':14s} | {'Error ($)':10s} | {'Error (%)':10s} | {'CI 80%?':8s}")
            print("-" * 92)
            show_indices = list(range(min(4, len(steps))))
            if len(steps) > 8:
                show_indices += list(range(len(steps) - 4, len(steps)))
            else:
                show_indices = list(range(len(steps)))

            last_idx = -1
            for idx in sorted(set(show_indices)):
                if last_idx != -1 and idx > last_idx + 1:
                    print(f"{'...':4s} | {'...':20s} | {'...':14s} | {'...':14s} | {'...':10s} | {'...':10s} | {'...':8s}")
                st = steps[idx]
                in_ci_str = "✅ Ya" if st["in_ci80"] else "⚠️ Di Luar"
                print(f"{st['step']:4d} | {st['datetime']:20s} | ${st['actual_close']:12,.4f} | ${st['pred_close']:12,.4f} | ${st['error_usd']:8,.4f} | {st['error_pct']:8.2f}% | {in_ci_str:8s}")
                last_idx = idx
            print("-" * 92)

            if args.out_json:
                with open(args.out_json, "w", encoding="utf-8") as f:
                    json.dump(res, f, indent=2)
                print(f"\n💾 Detail lengkap disimpan ke: {args.out_json}")

        elif args.subcommand == "web":
            from src.web_server import run_server
            run_server(host=args.host, port=args.port, reload=args.reload)

    except KeyboardInterrupt:
        print("\n[!] Dibatalkan oleh pengguna.", file=sys.stderr)
        sys.exit(130)
    except Exception as e:
        print(f"\n[❌ ERROR]: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
