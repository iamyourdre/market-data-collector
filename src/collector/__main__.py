"""
CLI Runner for Market Data Collector Sub-feature.
Allows executing: python -m src.collector
"""

import argparse
import sys
from .binance import setup_collector_cli_args, run_collector_cli


def main():
    parser = argparse.ArgumentParser(
        description="Binance Market Data Collector (Sub-fitur)"
    )
    setup_collector_cli_args(parser)
    args = parser.parse_args()

    try:
        run_collector_cli(args)
    except KeyboardInterrupt:
        print("\n[!] Dibatalkan oleh pengguna.", file=sys.stderr)
        sys.exit(130)
    except Exception as e:
        print(f"\n[❌ ERROR]: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
