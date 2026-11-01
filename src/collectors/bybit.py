"""
Bybit v5 Market Data Collector.
Fetches OHLCV, Funding Rates, and Open Interest from Bybit v5 public REST API.
No API key required (100% Free Tier).
"""

from datetime import datetime, timezone
import logging
import time
from typing import Any, Dict, List, Optional
import pandas as pd
import requests

from .base import BaseMarketDataCollector

logger = logging.getLogger(__name__)


class BybitFuturesCollector(BaseMarketDataCollector):
    """Collector for Bybit USDT Linear Perpetual Contracts (api.bybit.com)."""

    BASE_URL = "https://api.bybit.com"

    # Map timeframe string to Bybit interval parameter
    TIMEFRAME_MAP = {
        "15m": "15",
        "4h": "240",
        "1d": "D",
    }

    # Map timeframe string to Bybit Open Interest interval parameter
    OI_INTERVAL_MAP = {
        "15m": "15min",
        "4h": "4h",
        "1d": "1d",
    }

    def __init__(self, session: Optional[requests.Session] = None):
        super().__init__(exchange_name="bybit")
        self.session = session or requests.Session()
        self.session.headers.update(
            {"User-Agent": "CryptoMarketDataCollector/1.0", "Accept": "application/json"}
        )

    def _request(self, endpoint: str, params: Dict[str, Any], retries: int = 3) -> Any:
        url = f"{self.BASE_URL}{endpoint}"
        for attempt in range(1, retries + 1):
            try:
                resp = self.session.get(url, params=params, timeout=10)
                if resp.status_code == 200:
                    payload = resp.json()
                    if payload.get("retCode") == 0:
                        return payload.get("result", {})
                    else:
                        logger.warning(f"Bybit API retCode {payload.get('retCode')}: {payload.get('retMsg')}")
                elif resp.status_code == 429:
                    logger.warning("Rate limited by Bybit (429). Sleeping 2s...")
                    time.sleep(2.0)
                else:
                    logger.warning(f"Bybit HTTP error {resp.status_code}: {resp.text}")
            except Exception as e:
                logger.warning(f"Network error requesting {url}: {e} (attempt {attempt}/{retries})")

            time.sleep(1.0 * attempt)

        raise RuntimeError(f"Failed to fetch {url} after {retries} retries with params {params}")

    def fetch_ohlcv(
        self,
        symbol: str,
        timeframe: str,
        start_time_ms: int,
        end_time_ms: int,
    ) -> pd.DataFrame:
        """Fetch candlesticks using backward pagination (newest to oldest)."""
        endpoint = "/v5/market/kline"
        interval = self.TIMEFRAME_MAP.get(timeframe, "15")
        all_candles: List[List[Any]] = []
        current_end = end_time_ms
        limit = 200

        while current_end > start_time_ms:
            params = {
                "category": "linear",
                "symbol": symbol,
                "interval": interval,
                "start": start_time_ms,
                "end": current_end,
                "limit": limit,
            }
            result = self._request(endpoint, params)
            items = result.get("list", [])
            if not items:
                break

            all_candles.extend(items)
            oldest_time = int(items[-1][0])
            if len(items) < limit or oldest_time <= start_time_ms:
                break

            current_end = oldest_time - 1
            time.sleep(0.05)

        if not all_candles:
            return pd.DataFrame()

        # Bybit format: [startTime, openPrice, highPrice, lowPrice, closePrice, volume, turnover]
        df = pd.DataFrame(
            all_candles,
            columns=[
                "timestamp",
                "open",
                "high",
                "low",
                "close",
                "volume",
                "quote_volume",
            ],
        )

        df["timestamp"] = df["timestamp"].astype(int)
        for col in ["open", "high", "low", "close", "volume", "quote_volume"]:
            df[col] = df[col].astype(float)

        df["datetime"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True).dt.strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )

        df = df.drop_duplicates(subset=["timestamp"]).sort_values("timestamp").reset_index(drop=True)
        return df

    def fetch_funding_rates(
        self,
        symbol: str,
        start_time_ms: int,
        end_time_ms: int,
    ) -> List[Dict[str, Any]]:
        """Fetch funding rates from Bybit v5."""
        endpoint = "/v5/market/funding/history"
        all_funding: List[Dict[str, Any]] = []
        current_end = end_time_ms
        limit = 200

        while current_end > start_time_ms:
            params = {
                "category": "linear",
                "symbol": symbol,
                "startTime": start_time_ms,
                "endTime": current_end,
                "limit": limit,
            }
            try:
                result = self._request(endpoint, params)
            except Exception as e:
                logger.warning(f"Error fetching Bybit funding rates: {e}")
                break

            items = result.get("list", [])
            if not items:
                break

            for item in items:
                ts = int(item["fundingRateTimestamp"])
                all_funding.append(
                    {
                        "timestamp": ts,
                        "datetime": datetime.fromtimestamp(ts / 1000, tz=timezone.utc).strftime(
                            "%Y-%m-%dT%H:%M:%SZ"
                        ),
                        "funding_rate": float(item["fundingRate"]),
                        "mark_price": 0.0,
                    }
                )

            oldest_time = int(items[-1]["fundingRateTimestamp"])
            if len(items) < limit or oldest_time <= start_time_ms:
                break

            current_end = oldest_time - 1
            time.sleep(0.05)

        # Sort ascending
        all_funding.sort(key=lambda x: x["timestamp"])
        return all_funding

    def fetch_open_interest(
        self,
        symbol: str,
        timeframe: str,
        start_time_ms: int,
        end_time_ms: int,
    ) -> List[Dict[str, Any]]:
        """Fetch open interest from Bybit v5 (supports full 90+ days)."""
        endpoint = "/v5/market/open-interest"
        interval = self.OI_INTERVAL_MAP.get(timeframe, "15min")
        all_oi: List[Dict[str, Any]] = []
        current_end = end_time_ms
        limit = 200

        while current_end > start_time_ms:
            params = {
                "category": "linear",
                "symbol": symbol,
                "intervalTime": interval,
                "startTime": start_time_ms,
                "endTime": current_end,
                "limit": limit,
            }
            try:
                result = self._request(endpoint, params)
            except Exception as e:
                logger.warning(f"Error fetching Bybit open interest: {e}")
                break

            items = result.get("list", [])
            if not items:
                break

            for item in items:
                ts = int(item["timestamp"])
                all_oi.append(
                    {
                        "timestamp": ts,
                        "datetime": datetime.fromtimestamp(ts / 1000, tz=timezone.utc).strftime(
                            "%Y-%m-%dT%H:%M:%SZ"
                        ),
                        "open_interest": float(item["openInterest"]),
                        "open_interest_usd": 0.0,  # Bybit returns coin quantity
                    }
                )

            oldest_time = int(items[-1]["timestamp"])
            if len(items) < limit or oldest_time <= start_time_ms:
                break

            current_end = oldest_time - 1
            time.sleep(0.05)

        all_oi.sort(key=lambda x: x["timestamp"])
        return all_oi
