"""
Configuration and constants for Crypto Market Data Collector.
"""

from dataclasses import dataclass, field
from typing import List


@dataclass
class IndicatorConfig:
    rsi_period: int = 14
    macd_fast: int = 12
    macd_slow: int = 26
    macd_signal: int = 9
    ema_periods: List[int] = field(default_factory=lambda: [20, 50, 200])


@dataclass
class CollectorConfig:
    symbol: str = "BTCUSDT"
    timeframe: str = "15m"  # 15m, 4h, 1d
    days: int = 90  # 3 months default
    source: str = "binance"  # binance or bybit
    output_dir: str = "data"
    export_json: bool = True
    export_csv: bool = False
    indicators: IndicatorConfig = field(default_factory=IndicatorConfig)
    enable_doh: bool = True
    warmup_candles: int = 200  # Extra candles fetched beforehand to prime EMA/RSI calculations


SUPPORTED_TIMEFRAMES = ["15m", "4h", "1d"]
SUPPORTED_SOURCES = ["binance", "bybit"]

# Common popular symbols helper
POPULAR_SYMBOLS = [
    "BTCUSDT",
    "ETHUSDT",
    "SOLUSDT",
    "BNBUSDT",
    "DOGEUSDT",
    "XRPUSDT",
    "ADAUSDT",
    "AVAXUSDT",
    "NEARUSDT",
    "SUIUSDT",
    "PEPEUSDT",
]


def normalize_symbol(symbol: str) -> str:
    """Normalize user input e.g. 'btc', 'btc/usdt', 'BTC' -> 'BTCUSDT'."""
    clean = symbol.upper().replace("/", "").replace("-", "").replace("_", "").strip()
    if not clean.endswith("USDT") and not clean.endswith("USD") and not clean.endswith("FDUSD"):
        clean += "USDT"
    return clean
