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

    args = parser.parse_args()

    if not args.subcommand:
        parser.print_help()
        sys.exit(0)

    try:
        if args.subcommand == "collect":
            run_collector_cli(args)
        elif args.subcommand == "forecast":
            from crypto_forecast_engine import ForecastConfig, CryptoForecastEngine
            import json

            print(f"🚀 Memulai Quantitative Forecast Engine...")
            print(f"📂 Dataset Input: {args.input}")
            print(f"⏱️  Horizon Steps: {args.horizon} | Monte Carlo: {args.mc_sims:,} paths")
            cfg = ForecastConfig(horizon_steps=args.horizon, mc_simulations=args.mc_sims)
            engine = CryptoForecastEngine(cfg)
            df = engine.load_json(args.input)
            print(f"   -> Terbaca {len(df)} candles ({df['datetime'].iloc[0]} -> {df['datetime'].iloc[-1]})")
            print(f"   -> Harga Penutupan Terakhir: ${df['close'].iloc[-1]:,.2f}")

            engine.build_features()
            metrics = engine.run_walk_forward_backtest()
            print("\n📊 Bobot Ensemble & Akurasi Walk-Forward:")
            for m_name, w in engine.ensemble_weights.items():
                print(f"   • {m_name:20s}: {w * 100:5.2f}% | Path RMSE: ${metrics[m_name]['RMSE_Path']:,.2f} | DA: {metrics[m_name]['DA_Avg']:.2f}%")
            ens_m = metrics["M6_Best_Ensemble"]
            print(f"   🎯 Ensemble Terbaik -> Path RMSE: ${ens_m['RMSE_Path']:,.2f} | Avg DA: {ens_m['DA_Avg']:.2f}%")

            df_fc = engine.generate_forecasts()
            barriers = engine.simulate_barrier_probabilities(df_fc)

            df_fc.to_csv(args.out_csv, index=False)
            with open(args.out_json, "w", encoding="utf-8") as f:
                json.dump({
                    "metadata": engine.metadata,
                    "ensemble_weights": engine.ensemble_weights,
                    "garch_params": engine.garch_params,
                    "backtest_metrics": metrics,
                    "barrier_probabilities": barriers,
                }, f, indent=2)
            print(f"\n✅ Selesai! Trajectory disimpan ke: {args.out_csv}")
            print(f"✅ Ringkasan disimpan ke: {args.out_json}")

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
