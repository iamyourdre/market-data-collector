#!/usr/bin/env python3
"""
Crypto Market Data Collector CLI.
Collects OHLCV, RSI, MACD, EMA, Volume, Funding Rate, and Open Interest.
"""

import argparse
import http.server
import json
import logging
import os
from pathlib import Path
import socketserver
import sys
import webbrowser

# Enable DoH early to prevent DNS hijacking
from src.network.doh import enable_doh, disable_doh
from src.config import (
    CollectorConfig,
    SUPPORTED_TIMEFRAMES,
    SUPPORTED_SOURCES,
    POPULAR_SYMBOLS,
    normalize_symbol,
)
from src.collectors.binance import BinanceFuturesCollector
from src.collectors.bybit import BybitFuturesCollector
from src.storage.exporter import export_data

from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeElapsedColumn
from rich.table import Table
from rich.prompt import Prompt, Confirm

console = Console()
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")


def print_banner():
    banner = """
  [bold cyan]╔═══════════════════════════════════════════════════════════════╗[/bold cyan]
  [bold cyan]║[/bold cyan]       [bold yellow]⚡ CRYPTO MARKET DATA COLLECTOR[/bold yellow] (Free Tier)          [bold cyan]║[/bold cyan]
  [bold cyan]║[/bold cyan]  [dim]OHLCV • RSI • MACD • EMA • Volume • Funding Rate • Open Int[/dim]  [bold cyan]║[/bold cyan]
  [bold cyan]╚═══════════════════════════════════════════════════════════════╝[/bold cyan]
"""
    console.print(banner)


def run_collection(config: CollectorConfig, output_path: str = None) -> dict:
    """Execute data collection workflow with rich progress tracking."""
    if config.enable_doh:
        enable_doh()

    # Select collector
    if config.source.lower() == "binance":
        collector = BinanceFuturesCollector()
    elif config.source.lower() == "bybit":
        collector = BybitFuturesCollector()
    else:
        raise ValueError(f"Unsupported exchange source: {config.source}")

    console.print(
        f"\n[bold green]► Starting Data Collection[/bold green] for [bold yellow]{config.symbol}[/bold yellow] "
        f"on [bold magenta]{config.source.upper()}[/bold magenta] | Timeframe: [bold cyan]{config.timeframe}[/bold cyan] | Period: [bold]{config.days} days[/bold]"
    )

    with Progress(
        SpinnerColumn(),
        TextColumn("[bold blue]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        TimeElapsedColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("Initializing...", total=100)

        def progress_cb(description: str, ratio: float):
            progress.update(task, description=description, completed=int(ratio * 100))

        result = collector.collect(config, progress_callback=progress_cb)

    # Export to files
    saved = export_data(result, output_path=output_path, export_csv=config.export_csv)

    # Display Summary Table
    display_summary(result, saved)
    return saved


def display_summary(result, saved_paths: dict):
    """Print an attractive summary table of collected data."""
    df = result.df_merged
    cfg = result.config

    table = Table(title=f"📊 Collection Summary: {result.symbol} ({result.exchange.upper()})", show_header=True)
    table.add_column("Metric", style="cyan", no_wrap=True)
    table.add_column("Value", style="green")

    table.add_row("Timeframe", result.timeframe)
    table.add_row("Historical Range", f"{result.start_time.strftime('%Y-%m-%d')} to {result.end_time.strftime('%Y-%m-%d')} ({cfg.days} days)")
    table.add_row("Total Candlesticks", f"{len(df):,}")
    table.add_row("Highest Price", f"${df['high'].max():,.2f}")
    table.add_row("Lowest Price", f"${df['low'].min():,.2f}")
    table.add_row("Latest Close", f"${df['close'].iloc[-1]:,.2f}")

    if f"rsi_{cfg.indicators.rsi_period}" in df.columns:
        latest_rsi = df[f"rsi_{cfg.indicators.rsi_period}"].iloc[-1]
        table.add_row(f"Latest RSI({cfg.indicators.rsi_period})", f"{latest_rsi:.2f}")

    if "macd_line" in df.columns:
        latest_macd = df["macd_line"].iloc[-1]
        latest_sig = df["macd_signal"].iloc[-1]
        table.add_row("Latest MACD", f"Line: {latest_macd:.2f} | Signal: {latest_sig:.2f}")

    for p in cfg.indicators.ema_periods:
        if f"ema_{p}" in df.columns:
            table.add_row(f"EMA {p}", f"${df[f'ema_{p}'].iloc[-1]:,.2f}")

    table.add_row("Total Funding Events", f"{len(result.raw_funding_rates):,}")
    if result.raw_funding_rates:
        latest_fr = result.raw_funding_rates[-1]["funding_rate"]
        table.add_row("Latest Funding Rate", f"{latest_fr * 100:+.4f}%")

    table.add_row("Total Open Interest Points", f"{len(result.raw_open_interest):,}")
    if result.raw_open_interest:
        latest_oi = result.raw_open_interest[-1]["open_interest"]
        table.add_row("Latest Open Interest", f"{latest_oi:,.2f} contracts/coins")

    console.print("\n", table)

    # Output file paths
    file_info = "\n".join([f"• [bold]{k.upper()}:[/bold] [yellow]{v}[/yellow] ({os.path.getsize(v) / 1024:.1f} KB)" for k, v in saved_paths.items()])
    console.print(Panel(file_info, title="💾 Saved Files", border_style="cyan"))


def interactive_wizard():
    """Interactive CLI prompt when no arguments are provided."""
    print_banner()

    console.print("[bold]Pilih atau ketik koin cryptocurrency yang ingin dikumpulkan:[/bold]")
    console.print("[dim]Contoh populer: BTC, ETH, SOL, DOGE, BNB, XRP, SUI, ADA[/dim]")
    symbol_input = Prompt.ask("Masukkan Koin", default="BTC")
    symbol = normalize_symbol(symbol_input)

    console.print("\n[bold]Pilih Timeframe:[/bold]")
    timeframe = Prompt.ask("Timeframe", choices=["15m", "4h", "1d"], default="15m")

    console.print("\n[bold]Pilih Sumber Data (Free Tier API):[/bold]")
    console.print("  [bold cyan]1. Binance Futures[/bold cyan] (Likuiditas tertinggi, OHLCV + Funding Rate 90h + OI 30h)")
    console.print("  [bold cyan]2. Bybit Futures[/bold cyan]   (Full 90 hari untuk OHLCV, Funding Rate & Open Interest)")
    source_choice = Prompt.ask("Pilih sumber", choices=["1", "2", "binance", "bybit"], default="1")
    source = "binance" if source_choice in ["1", "binance"] else "bybit"

    days_str = Prompt.ask("\nPeriode Historis (hari)", default="90")
    days = int(days_str)

    export_csv = Confirm.ask("\nEkspor juga ke format CSV selain JSON?", default=False)

    config = CollectorConfig(
        symbol=symbol,
        timeframe=timeframe,
        days=days,
        source=source,
        export_csv=export_csv,
    )

    run_collection(config)


def start_web_server(port: int = 8080, open_browser: bool = True):
    """Launch a lightweight web server for the interactive dashboard."""
    base_dir = Path(__file__).parent.resolve()
    web_dir = base_dir / "src" / "web"
    data_dir = base_dir / "data"

    class CustomHandler(http.server.SimpleHTTPRequestHandler):
        def do_GET(self):
            if self.path == "/api/datasets":
                files = []
                if data_dir.exists():
                    for f in sorted(data_dir.glob("*.json"), key=os.path.getmtime, reverse=True):
                        files.append({"filename": f.name, "path": f"/data/{f.name}", "size_kb": round(f.stat().st_size / 1024, 1)})
                payload = json.dumps(files).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)
                return
            return super().do_GET()

        def translate_path(self, path):
            # Clean query string
            path = path.split("?")[0].split("#")[0]
            if path in ["/", "/index.html"]:
                return str(web_dir / "index.html")
            elif path.startswith("/data/"):
                rel_path = path[len("/data/"):]
                return str(data_dir / rel_path)
            elif (web_dir / path.lstrip("/")).exists():
                return str(web_dir / path.lstrip("/"))
            return str(base_dir / path.lstrip("/"))

    socketserver.TCPServer.allow_reuse_address = True
    console.print(f"\n[bold green]🚀 Web Dashboard aktif di:[/bold green] [bold cyan]http://localhost:{port}[/bold cyan]")
    console.print("[dim]Tekan Ctrl+C untuk berhenti.[/dim]\n")

    if open_browser:
        try:
            webbrowser.open(f"http://localhost:{port}")
        except Exception:
            pass

    with socketserver.TCPServer(("", port), CustomHandler) as httpd:
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            console.print("\n[yellow]Web server dihentikan.[/yellow]")


def main():
    parser = argparse.ArgumentParser(
        description="Crypto Market Data Collector (OHLCV, RSI, MACD, EMA, Funding Rate, Open Interest)"
    )
    parser.add_argument("-s", "--symbol", type=str, help="Coin symbol (e.g. BTC, ETH, SOL, BTCUSDT)")
    parser.add_argument("-t", "--timeframe", type=str, choices=SUPPORTED_TIMEFRAMES, help="Timeframe (15m, 4h, 1d)")
    parser.add_argument("-d", "--days", type=int, default=90, help="Historical period in days (default: 90)")
    parser.add_argument("--source", type=str, choices=SUPPORTED_SOURCES, default="binance", help="Data source exchange (default: binance)")
    parser.add_argument("-o", "--output", type=str, help="Custom output JSON file path")
    parser.add_argument("--csv", action="store_true", help="Also export to CSV format")
    parser.add_argument("--no-doh", action="store_true", help="Disable built-in DNS-over-HTTPS resolver")
    parser.add_argument("--serve", action="store_true", help="Start local visual dashboard web server")
    parser.add_argument("--port", type=int, default=8080, help="Port for web dashboard server (default: 8080)")
    parser.add_argument("--no-browser", action="store_true", help="Do not automatically open web browser")

    args = parser.parse_args()

    if args.serve:
        start_web_server(port=args.port, open_browser=not args.no_browser)
        return

    # If no parameters provided, run interactive wizard
    if not args.symbol and not args.timeframe:
        interactive_wizard()
        return

    print_banner()
    symbol = normalize_symbol(args.symbol or "BTCUSDT")
    timeframe = args.timeframe or "15m"

    config = CollectorConfig(
        symbol=symbol,
        timeframe=timeframe,
        days=args.days,
        source=args.source,
        export_csv=args.csv,
        enable_doh=not args.no_doh,
    )

    run_collection(config, output_path=args.output)


if __name__ == "__main__":
    main()
