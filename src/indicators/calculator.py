"""
Technical Indicator Calculations using pandas and numpy.
Implements standard formulas compatible with TradingView.
"""

import logging
import numpy as np
import pandas as pd
from typing import List, Optional
from ..config import IndicatorConfig

logger = logging.getLogger(__name__)


def calculate_rsi(series: pd.Series, period: int = 14) -> pd.Series:
    """Calculate Relative Strength Index (RSI) using Wilder's smoothing method."""
    delta = series.diff()
    gain = delta.clip(lower=0.0)
    loss = (-delta).clip(lower=0.0)

    # Wilder's Smoothing is an EMA with alpha = 1 / period
    avg_gain = gain.ewm(alpha=1.0 / period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1.0 / period, min_periods=period, adjust=False).mean()

    # Avoid division by zero
    rs = np.where(avg_loss == 0, 100.0, avg_gain / avg_loss)
    rsi = 100.0 - (100.0 / (1.0 + rs))

    # Where both gain and loss are 0, RSI is 50.0
    rsi = np.where((avg_gain == 0) & (avg_loss == 0), 50.0, rsi)

    return pd.Series(rsi, index=series.index)


def calculate_macd(
    series: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9
) -> pd.DataFrame:
    """Calculate MACD Line, Signal Line, and MACD Histogram."""
    ema_fast = series.ewm(span=fast, adjust=False).mean()
    ema_slow = series.ewm(span=slow, adjust=False).mean()

    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    histogram = macd_line - signal_line

    return pd.DataFrame(
        {
            "macd": macd_line,
            "macd_signal": signal_line,
            "macd_hist": histogram,
        },
        index=series.index,
    )


def calculate_ema(series: pd.Series, periods: List[int]) -> pd.DataFrame:
    """Calculate Exponential Moving Averages for given periods."""
    result = {}
    for p in periods:
        result[f"ema_{p}"] = series.ewm(span=p, adjust=False).mean()
    return pd.DataFrame(result, index=series.index)


def compute_all_indicators(
    df: pd.DataFrame,
    config: Optional[IndicatorConfig] = None,
) -> pd.DataFrame:
    """
    Compute RSI, MACD, and EMA indicators on a DataFrame containing 'close' and 'volume'.
    Returns a new DataFrame enriched with technical indicator columns.
    """
    cfg = config or IndicatorConfig()
    result = df.copy()

    if "close" not in result.columns:
        raise ValueError("DataFrame must contain a 'close' column to compute indicators.")

    close = result["close"].astype(float)

    # 1. RSI
    result[f"rsi_{cfg.rsi_period}"] = calculate_rsi(close, period=cfg.rsi_period)

    # 2. MACD
    macd_df = calculate_macd(
        close, fast=cfg.macd_fast, slow=cfg.macd_slow, signal=cfg.macd_signal
    )
    result["macd_line"] = macd_df["macd"]
    result["macd_signal"] = macd_df["macd_signal"]
    result["macd_hist"] = macd_df["macd_hist"]

    # 3. EMA
    ema_df = calculate_ema(close, periods=cfg.ema_periods)
    for col in ema_df.columns:
        result[col] = ema_df[col]

    # 4. Volume indicators (SMA 20)
    if "volume" in result.columns:
        result["volume_sma_20"] = (
            result["volume"].astype(float).rolling(window=20, min_periods=1).mean()
        )

    logger.debug(f"Computed indicators for {len(result)} candles.")
    return result
