"""
Abstract Base Collector for Crypto Market Data.
Defines common interfaces and data harmonization across exchanges.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timezone
import logging
from typing import Any, Dict, List, Optional
import pandas as pd

from ..config import CollectorConfig
from ..indicators.calculator import compute_all_indicators

logger = logging.getLogger(__name__)


@dataclass
class CollectionResult:
    symbol: str
    timeframe: str
    exchange: str
    start_time: datetime
    end_time: datetime
    df_merged: pd.DataFrame
    raw_funding_rates: List[Dict[str, Any]]
    raw_open_interest: List[Dict[str, Any]]
    config: CollectorConfig


class BaseMarketDataCollector(ABC):
    """Base class for cryptocurrency market data collectors."""

    def __init__(self, exchange_name: str):
        self.exchange_name = exchange_name

    @abstractmethod
    def fetch_ohlcv(
        self,
        symbol: str,
        timeframe: str,
        start_time_ms: int,
        end_time_ms: int,
    ) -> pd.DataFrame:
        """Fetch historical candlestick data with pagination."""
        pass

    @abstractmethod
    def fetch_funding_rates(
        self,
        symbol: str,
        start_time_ms: int,
        end_time_ms: int,
    ) -> List[Dict[str, Any]]:
        """Fetch historical funding rate records."""
        pass

    @abstractmethod
    def fetch_open_interest(
        self,
        symbol: str,
        timeframe: str,
        start_time_ms: int,
        end_time_ms: int,
    ) -> List[Dict[str, Any]]:
        """Fetch historical open interest records."""
        pass

    def collect(
        self,
        config: CollectorConfig,
        progress_callback=None,
    ) -> CollectionResult:
        """
        Orchestrate complete data collection:
        1. Calculate start/end timestamps (with warmup buffer).
        2. Fetch OHLCV candles.
        3. Compute indicators (RSI, MACD, EMA).
        4. Trim warmup candles to exact requested date window.
        5. Fetch Funding Rates & Open Interest.
        6. Align/merge derivatives metrics with candles.
        """
        now_dt = datetime.now(timezone.utc)
        end_time_ms = int(now_dt.timestamp() * 1000)
        requested_start_ms = end_time_ms - (config.days * 24 * 3600 * 1000)

        # Calculate warmup time offset based on timeframe
        warmup_ms = self._get_warmup_duration_ms(config.timeframe, config.warmup_candles)
        fetch_start_ms = requested_start_ms - warmup_ms

        logger.info(
            f"Collecting {config.symbol} on {self.exchange_name} ({config.timeframe}) "
            f"for {config.days} days..."
        )

        # 1. Fetch OHLCV
        if progress_callback:
            progress_callback("Fetching OHLCV Candlesticks...", 0.1)
        df_candles = self.fetch_ohlcv(
            symbol=config.symbol,
            timeframe=config.timeframe,
            start_time_ms=fetch_start_ms,
            end_time_ms=end_time_ms,
        )

        if df_candles.empty:
            raise ValueError(f"No OHLCV candles returned for {config.symbol} on {self.exchange_name}")

        # 2. Compute Indicators
        if progress_callback:
            progress_callback("Calculating Technical Indicators (RSI, MACD, EMA)...", 0.4)
        df_enriched = compute_all_indicators(df_candles, config.indicators)

        # 3. Trim warmup candles (keep from requested_start_ms onwards)
        df_trimmed = df_enriched[df_enriched["timestamp"] >= requested_start_ms].copy()
        if df_trimmed.empty:
            df_trimmed = df_enriched.copy()

        # 4. Fetch Funding Rates
        if progress_callback:
            progress_callback("Fetching Funding Rate History...", 0.6)
        raw_funding = self.fetch_funding_rates(
            symbol=config.symbol,
            start_time_ms=requested_start_ms,
            end_time_ms=end_time_ms,
        )

        # 5. Fetch Open Interest
        if progress_callback:
            progress_callback("Fetching Open Interest History...", 0.8)
        raw_oi = self.fetch_open_interest(
            symbol=config.symbol,
            timeframe=config.timeframe,
            start_time_ms=requested_start_ms,
            end_time_ms=end_time_ms,
        )

        # 6. Merge Derivatives with Candles
        if progress_callback:
            progress_callback("Harmonizing & Merging Derivatives Data...", 0.95)
        df_final = self._merge_derivatives(df_trimmed, raw_funding, raw_oi, config.timeframe)

        if progress_callback:
            progress_callback("Complete!", 1.0)

        start_dt = datetime.fromtimestamp(requested_start_ms / 1000, tz=timezone.utc)
        return CollectionResult(
            symbol=config.symbol,
            timeframe=config.timeframe,
            exchange=self.exchange_name,
            start_time=start_dt,
            end_time=now_dt,
            df_merged=df_final,
            raw_funding_rates=raw_funding,
            raw_open_interest=raw_oi,
            config=config,
        )

    def _get_warmup_duration_ms(self, timeframe: str, candles: int) -> int:
        multiplier = {
            "15m": 15 * 60 * 1000,
            "4h": 4 * 3600 * 1000,
            "1d": 24 * 3600 * 1000,
        }.get(timeframe, 15 * 60 * 1000)
        return candles * multiplier

    def _merge_derivatives(
        self,
        df: pd.DataFrame,
        funding_rates: List[Dict[str, Any]],
        open_interest: List[Dict[str, Any]],
        timeframe: str,
    ) -> pd.DataFrame:
        """Merge funding rates and open interest into the candle DataFrame."""
        result = df.copy()

        # Default columns
        result["open_interest"] = None
        result["open_interest_usd"] = None
        result["funding_rate"] = None
        result["funding_settled"] = None

        # Prepare Open Interest DataFrame
        if open_interest:
            df_oi = pd.DataFrame(open_interest)
            if "timestamp" in df_oi.columns:
                df_oi["timestamp"] = df_oi["timestamp"].astype(int)
                # Sort and remove duplicates
                df_oi = df_oi.drop_duplicates(subset=["timestamp"]).sort_values("timestamp")

                # Merge asof / nearest on candle timestamp
                result = pd.merge_asof(
                    result.sort_values("timestamp"),
                    df_oi[["timestamp", "open_interest", "open_interest_usd"]],
                    on="timestamp",
                    direction="nearest",
                    tolerance=self._get_warmup_duration_ms(timeframe, 1),
                    suffixes=("", "_from_oi"),
                )
                if "open_interest_from_oi" in result.columns:
                    result["open_interest"] = result["open_interest_from_oi"]
                    result = result.drop(columns=["open_interest_from_oi"])
                if "open_interest_usd_from_oi" in result.columns:
                    result["open_interest_usd"] = result["open_interest_usd_from_oi"]
                    result = result.drop(columns=["open_interest_usd_from_oi"])

        # Prepare Funding Rate DataFrame
        if funding_rates:
            df_fr = pd.DataFrame(funding_rates)
            if "timestamp" in df_fr.columns:
                df_fr["timestamp"] = df_fr["timestamp"].astype(int)
                df_fr = df_fr.drop_duplicates(subset=["timestamp"]).sort_values("timestamp")
                df_fr["funding_settled"] = df_fr["funding_rate"]

                # Merge exact or asof funding rate (settlement point & active rate)
                merged = pd.merge_asof(
                    result.sort_values("timestamp"),
                    df_fr[["timestamp", "funding_rate"]],
                    on="timestamp",
                    direction="backward",
                    suffixes=("", "_active"),
                )
                if "funding_rate_active" in merged.columns:
                    result["funding_rate"] = merged["funding_rate_active"]

                # Mark specific candles that had actual funding settlement
                exact_fr = pd.merge_asof(
                    result.sort_values("timestamp"),
                    df_fr[["timestamp", "funding_settled"]],
                    on="timestamp",
                    direction="nearest",
                    tolerance=self._get_warmup_duration_ms(timeframe, 1),
                    suffixes=("", "_match"),
                )
                if "funding_settled_match" in exact_fr.columns:
                    result["funding_settled"] = exact_fr["funding_settled_match"]

        return result
