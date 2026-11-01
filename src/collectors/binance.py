"""
Binance Futures Market Data Collector.
Fetches OHLCV, Funding Rates, and Open Interest from Binance USD-M Futures public REST API.
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


class BinanceFuturesCollector(BaseMarketDataCollector):
    """Collector for Binance USD-M Futures (fapi.binance.com)."""

    BASE_URL = "https://fapi.binance.com"

    def __init__(self, session: Optional[requests.Session] = None):
        super().__init__(exchange_name="binance")
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
                    return resp.json()
                elif resp.status_code == 429:
                    retry_after = int(resp.headers.get("Retry-After", 2))
                    logger.warning(f"Rate limited by Binance (429). Backing off for {retry_after}s...")
                    time.sleep(retry_after)
                else:
                    logger.warning(
                        f"Binance API error {resp.status_code}: {resp.text} (attempt {attempt}/{retries})"
                    )
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
        """
        Fetch historical klines (candlesticks) using pagination.
        Binance returns max 1500 klines per call.
        """
        endpoint = "/fapi/v1/klines"
        all_candles: List[List[Any]] = []
        current_start = start_time_ms
        limit = 1500

        while current_start < end_time_ms:
            params = {
                "symbol": symbol,
                "interval": timeframe,
                "startTime": current_start,
                "endTime": end_time_ms,
                "limit": limit,
            }
            data = self._request(endpoint, params)
            if not data or not isinstance(data, list):
                break

            all_candles.extend(data)
            logger.debug(
                f"Binance {symbol} klines fetched {len(data)}, total: {len(all_candles)}"
            )

            # Last candle open_time is at index 0
            last_open_time = data[-1][0]
            if len(data) < limit or last_open_time <= current_start:
                break

            current_start = last_open_time + 1
            time.sleep(0.05)  # Politeness interval

        if not all_candles:
            return pd.DataFrame()

        # Parse into standard DataFrame
        df = pd.DataFrame(
            all_candles,
            columns=[
                "timestamp",
                "open",
                "high",
                "low",
                "close",
                "volume",
                "close_time",
                "quote_volume",
                "trades_count",
                "taker_buy_base_volume",
                "taker_buy_quote_volume",
                "ignore",
            ],
        )

        # Convert datatypes
        df["timestamp"] = df["timestamp"].astype(int)
        df["close_time"] = df["close_time"].astype(int)
        for col in ["open", "high", "low", "close", "volume", "quote_volume"]:
            df[col] = df[col].astype(float)
        df["trades_count"] = df["trades_count"].astype(int)

        # Human-readable datetime ISO 8601
        df["datetime"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True).dt.strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )

        # Deduplicate and sort
        df = df.drop_duplicates(subset=["timestamp"]).sort_values("timestamp").reset_index(drop=True)
        return df

    def fetch_funding_rates(
        self,
        symbol: str,
        start_time_ms: int,
        end_time_ms: int,
    ) -> List[Dict[str, Any]]:
        """
        Fetch historical funding rates using pagination.
        Binance returns max 1000 records per call.
        """
        endpoint = "/fapi/v1/fundingRate"
        all_funding: List[Dict[str, Any]] = []
        current_start = start_time_ms
        limit = 1000

        while current_start < end_time_ms:
            params = {
                "symbol": symbol,
                "startTime": current_start,
                "endTime": end_time_ms,
                "limit": limit,
            }
            try:
                data = self._request(endpoint, params)
            except Exception as e:
                logger.warning(f"Error fetching funding rates: {e}")
                break

            if not data or not isinstance(data, list):
                break

            for item in data:
                all_funding.append(
                    {
                        "timestamp": int(item["fundingTime"]),
                        "datetime": datetime.fromtimestamp(
                            int(item["fundingTime"]) / 1000, tz=timezone.utc
                        ).strftime("%Y-%m-%dT%H:%M:%SZ"),
                        "funding_rate": float(item["fundingRate"]),
                        "mark_price": float(item.get("markPrice", 0.0)),
                    }
                )

            last_time = int(data[-1]["fundingTime"])
            if len(data) < limit or last_time <= current_start:
                break

            current_start = last_time + 1
            time.sleep(0.05)

        logger.debug(f"Binance {symbol} total funding records: {len(all_funding)}")
        return all_funding

    def fetch_open_interest(
        self,
        symbol: str,
        timeframe: str,
        start_time_ms: int,
        end_time_ms: int,
    ) -> List[Dict[str, Any]]:
        """
        Fetch historical open interest using pagination.
        Note: Binance public endpoint `/futures/data/openInterestHist` allows data up to 30 days back.
        We clamp the start date to ~29.5 days ago to prevent 400 invalid startTime error.
        """
        endpoint = "/futures/data/openInterestHist"
        all_oi: List[Dict[str, Any]] = []

        now_ms = int(time.time() * 1000)
        max_allowed_start = now_ms - (29 * 24 * 3600 * 1000)
        clamped_start = max(start_time_ms, max_allowed_start)

        current_start = clamped_start
        limit = 500

        # Binance period options: 5m, 15m, 30m, 1h, 2h, 4h, 6h, 12h, 1d
        period_map = {"15m": "15m", "4h": "4h", "1d": "1d"}
        period = period_map.get(timeframe, "15m")

        while current_start < end_time_ms:
            params = {
                "symbol": symbol,
                "period": period,
                "startTime": current_start,
                "endTime": end_time_ms,
                "limit": limit,
            }
            try:
                data = self._request(endpoint, params)
            except Exception as e:
                logger.warning(f"Error fetching open interest: {e}")
                break

            if not data or not isinstance(data, list):
                break

            for item in data:
                all_oi.append(
                    {
                        "timestamp": int(item["timestamp"]),
                        "datetime": datetime.fromtimestamp(
                            int(item["timestamp"]) / 1000, tz=timezone.utc
                        ).strftime("%Y-%m-%dT%H:%M:%SZ"),
                        "open_interest": float(item["sumOpenInterest"]),
                        "open_interest_usd": float(item["sumOpenInterestValue"]),
                    }
                )

            last_time = int(data[-1]["timestamp"])
            if len(data) < limit or last_time <= current_start:
                break

            current_start = last_time + 1
            time.sleep(0.05)

        logger.debug(f"Binance {symbol} total open interest records: {len(all_oi)}")
        return all_oi
