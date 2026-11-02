"""
Binance Market Data Collector Module.
Fetches OHLCV, Funding Rates, and Open Interest from Binance Futures public API.
Requires no API key (Free Tier).
"""

import bisect
from datetime import datetime, timezone
import json
import logging
import os
from pathlib import Path
import socket
import time
from typing import Any, Callable, Dict, List, Optional
import urllib.request
import requests

logger = logging.getLogger(__name__)

# DNS-over-HTTPS (DoH) support to prevent ISP DNS blocking/hijacking
_REAL_GETADDRINFO = socket.getaddrinfo
_DOH_CACHE: Dict[str, List[str]] = {}
_DOH_ENABLED = False


def resolve_doh(domain: str, timeout: float = 3.0) -> List[str]:
    """Resolve A record using Cloudflare or Google DoH."""
    if domain in _DOH_CACHE:
        return _DOH_CACHE[domain]

    # Cloudflare DoH
    try:
        req = urllib.request.Request(
            f"https://cloudflare-dns.com/dns-query?name={domain}&type=A",
            headers={"accept": "application/dns-json"},
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode())
            ips = [ans["data"] for ans in data.get("Answer", []) if ans.get("type") == 1]
            if ips:
                _DOH_CACHE[domain] = ips
                return ips
    except Exception as e:
        logger.debug(f"Cloudflare DoH resolution failed for {domain}: {e}")

    # Google DoH Fallback
    try:
        req = urllib.request.Request(
            f"https://dns.google/resolve?name={domain}&type=A",
            headers={"accept": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode())
            ips = [ans["data"] for ans in data.get("Answer", []) if ans.get("type") == 1]
            if ips:
                _DOH_CACHE[domain] = ips
                return ips
    except Exception as e:
        logger.debug(f"Google DoH resolution failed for {domain}: {e}")

    return []


def enable_doh(target_domains: Optional[List[str]] = None) -> None:
    """Enable DoH monkey-patch on socket.getaddrinfo for crypto domains."""
    global _DOH_ENABLED
    if _DOH_ENABLED:
        return

    domains = target_domains or ["binance.com", "fapi.binance.com", "api.binance.com"]

    def custom_getaddrinfo(host, port, family=0, type=0, proto=0, flags=0):
        if host and any(d in host for d in domains):
            ips = resolve_doh(host)
            if ips:
                return _REAL_GETADDRINFO(ips[0], port, family, type, proto, flags)
        return _REAL_GETADDRINFO(host, port, family, type, proto, flags)

    socket.getaddrinfo = custom_getaddrinfo
    _DOH_ENABLED = True
    logger.debug("DNS-over-HTTPS resolver enabled for Binance domains.")


def disable_doh() -> None:
    """Restore original socket.getaddrinfo."""
    global _DOH_ENABLED
    if _DOH_ENABLED:
        socket.getaddrinfo = _REAL_GETADDRINFO
        _DOH_ENABLED = False


def normalize_symbol(symbol: str) -> str:
    """Normalize input like 'btc', 'btc/usdt', 'BTC' -> 'BTCUSDT'."""
    clean = symbol.upper().replace("/", "").replace("-", "").replace("_", "").strip()
    if not any(clean.endswith(q) for q in ("USDT", "USD", "FDUSD", "BUSD")):
        clean += "USDT"
    return clean


class BinanceCollector:
    """Collector for Binance USD-M Futures public REST API."""

    BASE_URL = "https://fapi.binance.com"

    def __init__(
        self,
        session: Optional[requests.Session] = None,
        use_doh: bool = True,
        enable_doh_resolution: Optional[bool] = None,
    ):
        actual_doh = enable_doh_resolution if enable_doh_resolution is not None else use_doh
        if actual_doh:
            enable_doh()
        self.session = session or requests.Session()
        self.session.headers.update(
            {"User-Agent": "CryptoMarketDataCollector/2.0", "Accept": "application/json"}
        )

    def _request(self, endpoint: str, params: Dict[str, Any], retries: int = 3) -> Any:
        url = f"{self.BASE_URL}{endpoint}"
        for attempt in range(1, retries + 1):
            try:
                resp = self.session.get(url, params=params, timeout=12)
                if resp.status_code == 200:
                    return resp.json()
                elif resp.status_code == 429:
                    retry_after = int(resp.headers.get("Retry-After", 2))
                    logger.warning(f"Binance 429 rate limit. Backing off for {retry_after}s...")
                    time.sleep(retry_after)
                else:
                    logger.warning(
                        f"Binance API returned status {resp.status_code}: {resp.text} (attempt {attempt}/{retries})"
                    )
            except Exception as e:
                logger.warning(f"Network error requesting {url}: {e} (attempt {attempt}/{retries})")

            time.sleep(1.0 * attempt)

        raise RuntimeError(f"Failed to fetch {url} after {retries} retries with params {params}")

    def fetch_klines(
        self,
        symbol: str,
        interval: str,
        start_time_ms: int,
        end_time_ms: int,
        on_progress: Optional[Callable[[int], None]] = None,
    ) -> List[Dict[str, Any]]:
        """Fetch historical candlesticks (OHLCV) using pagination."""
        endpoint = "/fapi/v1/klines"
        candles: List[Dict[str, Any]] = []
        current_start = start_time_ms
        limit = 1500

        while current_start < end_time_ms:
            params = {
                "symbol": symbol,
                "interval": interval,
                "startTime": current_start,
                "endTime": end_time_ms,
                "limit": limit,
            }
            data = self._request(endpoint, params)
            if not data or not isinstance(data, list):
                break

            for c in data:
                open_ts = int(c[0])
                candles.append(
                    {
                        "timestamp": open_ts,
                        "datetime": datetime.fromtimestamp(open_ts / 1000, tz=timezone.utc).strftime(
                            "%Y-%m-%dT%H:%M:%SZ"
                        ),
                        "open": float(c[1]),
                        "high": float(c[2]),
                        "low": float(c[3]),
                        "close": float(c[4]),
                        "volume": float(c[5]),
                        "close_time": int(c[6]),
                        "quote_volume": float(c[7]),
                        "trades_count": int(c[8]),
                        "taker_buy_volume": float(c[9]),
                        "taker_buy_quote_volume": float(c[10]),
                    }
                )

            if on_progress:
                on_progress(len(candles))

            last_open = int(data[-1][0])
            if len(data) < limit or last_open <= current_start:
                break

            current_start = last_open + 1
            time.sleep(0.04)

        # Deduplicate & sort by timestamp
        seen = set()
        unique_candles = []
        for c in candles:
            if c["timestamp"] not in seen:
                seen.add(c["timestamp"])
                unique_candles.append(c)
        return sorted(unique_candles, key=lambda x: x["timestamp"])

    def fetch_funding_rates(
        self,
        symbol: str,
        start_time_ms: int,
        end_time_ms: int,
        on_progress: Optional[Callable[[int], None]] = None,
    ) -> List[Dict[str, Any]]:
        """Fetch historical funding rates using pagination."""
        endpoint = "/fapi/v1/fundingRate"
        rates: List[Dict[str, Any]] = []
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
                rates.append(
                    {
                        "timestamp": int(item["fundingTime"]),
                        "datetime": datetime.fromtimestamp(
                            int(item["fundingTime"]) / 1000, tz=timezone.utc
                        ).strftime("%Y-%m-%dT%H:%M:%SZ"),
                        "funding_rate": float(item["fundingRate"]),
                        "mark_price": float(item.get("markPrice", 0.0)),
                    }
                )

            if on_progress:
                on_progress(len(rates))

            last_time = int(data[-1]["fundingTime"])
            if len(data) < limit or last_time <= current_start:
                break

            current_start = last_time + 1
            time.sleep(0.04)

        seen = set()
        unique_rates = []
        for r in rates:
            if r["timestamp"] not in seen:
                seen.add(r["timestamp"])
                unique_rates.append(r)
        return sorted(unique_rates, key=lambda x: x["timestamp"])

    def fetch_open_interest(
        self,
        symbol: str,
        timeframe: str,
        start_time_ms: int,
        end_time_ms: int,
        on_progress: Optional[Callable[[int], None]] = None,
    ) -> List[Dict[str, Any]]:
        """Fetch historical open interest (Binance allows up to ~30 days back)."""
        endpoint = "/futures/data/openInterestHist"
        oi_list: List[Dict[str, Any]] = []

        now_ms = int(time.time() * 1000)
        max_allowed_start = now_ms - (29 * 24 * 3600 * 1000)
        clamped_start = max(start_time_ms, max_allowed_start)

        # Map timeframe to Binance valid OI period
        period_map = {
            "1m": "5m",
            "3m": "5m",
            "5m": "5m",
            "15m": "15m",
            "30m": "30m",
            "1h": "1h",
            "2h": "2h",
            "4h": "4h",
            "6h": "6h",
            "8h": "12h",
            "12h": "12h",
            "1d": "1d",
            "3d": "1d",
            "1w": "1d",
            "1M": "1d",
        }
        period = period_map.get(timeframe, "15m")
        current_start = clamped_start
        limit = 500

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
                oi_list.append(
                    {
                        "timestamp": int(item["timestamp"]),
                        "datetime": datetime.fromtimestamp(
                            int(item["timestamp"]) / 1000, tz=timezone.utc
                        ).strftime("%Y-%m-%dT%H:%M:%SZ"),
                        "open_interest": float(item["sumOpenInterest"]),
                        "open_interest_usd": float(item["sumOpenInterestValue"]),
                    }
                )

            if on_progress:
                on_progress(len(oi_list))

            last_time = int(data[-1]["timestamp"])
            if len(data) < limit or last_time <= current_start:
                break

            current_start = last_time + 1
            time.sleep(0.04)

        seen = set()
        unique_oi = []
        for item in oi_list:
            if item["timestamp"] not in seen:
                seen.add(item["timestamp"])
                unique_oi.append(item)
        return sorted(unique_oi, key=lambda x: x["timestamp"])

    def merge_derivatives(
        self,
        candles: List[Dict[str, Any]],
        funding_rates: List[Dict[str, Any]],
        open_interests: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Fast pure-Python alignment of funding rates and open interest to candles."""
        oi_timestamps = [item["timestamp"] for item in open_interests]
        fr_timestamps = [item["timestamp"] for item in funding_rates]

        for c in candles:
            c_ts = c["timestamp"]
            c_close = c["close_time"]
            candle_duration = max(1, c_close - c_ts)

            # Match nearest Open Interest within candle duration
            if oi_timestamps:
                idx = bisect.bisect_left(oi_timestamps, c_ts)
                best_oi = None
                min_diff = float("inf")
                for cand_idx in (idx - 1, idx, idx + 1):
                    if 0 <= cand_idx < len(oi_timestamps):
                        diff = abs(oi_timestamps[cand_idx] - c_ts)
                        if diff < min_diff and diff <= candle_duration:
                            min_diff = diff
                            best_oi = open_interests[cand_idx]
                if best_oi:
                    c["open_interest"] = best_oi["open_interest"]
                    c["open_interest_usd"] = best_oi["open_interest_usd"]
                else:
                    c["open_interest"] = None
                    c["open_interest_usd"] = None
            else:
                c["open_interest"] = None
                c["open_interest_usd"] = None

            # Match active Funding Rate & settlement event
            if fr_timestamps:
                active_idx = bisect.bisect_right(fr_timestamps, c_ts) - 1
                if 0 <= active_idx < len(funding_rates):
                    c["funding_rate"] = funding_rates[active_idx]["funding_rate"]
                else:
                    c["funding_rate"] = None

                settled_idx = bisect.bisect_left(fr_timestamps, c_ts)
                if 0 <= settled_idx < len(funding_rates) and fr_timestamps[settled_idx] <= c_close:
                    c["funding_settled"] = funding_rates[settled_idx]["funding_rate"]
                else:
                    c["funding_settled"] = None
            else:
                c["funding_rate"] = None
                c["funding_settled"] = None

        return candles

    def collect(
        self,
        symbol: str,
        timeframe: str = "15m",
        days: int = 30,
        status_cb: Optional[Callable[[str], None]] = None,
    ) -> Dict[str, Any]:
        """
        Orchestrate complete collection for symbol:
        1. Fetch OHLCV candles
        2. Fetch Funding Rates
        3. Fetch Open Interest
        4. Align data and compute summary stats
        Returns clean dictionary ready for JSON serialization.
        """
        norm_symbol = normalize_symbol(symbol)
        now_dt = datetime.now(timezone.utc)
        end_time_ms = int(now_dt.timestamp() * 1000)
        start_time_ms = end_time_ms - (days * 24 * 3600 * 1000)
        start_dt = datetime.fromtimestamp(start_time_ms / 1000, tz=timezone.utc)

        if status_cb:
            status_cb(f"Mengambil OHLCV ({norm_symbol}, {timeframe}, {days} hari)...")
        candles = self.fetch_klines(
            symbol=norm_symbol,
            interval=timeframe,
            start_time_ms=start_time_ms,
            end_time_ms=end_time_ms,
        )

        if not candles:
            raise ValueError(f"Tidak ada data candle yang ditemukan untuk {norm_symbol}")

        if status_cb:
            status_cb(f"Mengambil riwayat Funding Rate ({norm_symbol})...")
        funding_rates = self.fetch_funding_rates(
            symbol=norm_symbol,
            start_time_ms=start_time_ms,
            end_time_ms=end_time_ms,
        )

        if status_cb:
            status_cb(f"Mengambil riwayat Open Interest ({norm_symbol})...")
        open_interests = self.fetch_open_interest(
            symbol=norm_symbol,
            timeframe=timeframe,
            start_time_ms=start_time_ms,
            end_time_ms=end_time_ms,
        )

        if status_cb:
            status_cb("Menyelaraskan data derivatif dengan candlestick...")
        merged_candles = self.merge_derivatives(candles, funding_rates, open_interests)

        # Summary statistics
        start_price = merged_candles[0]["open"]
        latest_price = merged_candles[-1]["close"]
        highest_price = max(c["high"] for c in merged_candles)
        lowest_price = min(c["low"] for c in merged_candles)
        total_volume = sum(c["volume"] for c in merged_candles)
        total_quote_vol = sum(c["quote_volume"] for c in merged_candles)
        price_change_pct = (
            round(((latest_price - start_price) / start_price * 100), 2)
            if start_price > 0
            else 0.0
        )

        payload = {
            "metadata": {
                "symbol": norm_symbol,
                "exchange": "binance",
                "timeframe": timeframe,
                "period_days": days,
                "start_time": start_dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "end_time": now_dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "total_candles": len(merged_candles),
                "total_funding_events": len(funding_rates),
                "total_oi_records": len(open_interests),
                "summary_stats": {
                    "start_price": round(start_price, 4),
                    "latest_price": round(latest_price, 4),
                    "highest_price": round(highest_price, 4),
                    "lowest_price": round(lowest_price, 4),
                    "price_change_pct": price_change_pct,
                    "total_volume": round(total_volume, 4),
                    "total_quote_volume": round(total_quote_vol, 2),
                    "latest_funding_rate": funding_rates[-1]["funding_rate"]
                    if funding_rates
                    else None,
                    "latest_open_interest": open_interests[-1]["open_interest"]
                    if open_interests
                    else None,
                },
                "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            },
            "data": merged_candles,
            "raw_funding_rates": funding_rates,
            "raw_open_interest": open_interests,
        }
        return payload

    @staticmethod
    def save_json(payload: Dict[str, Any], filepath: str, indent: int = 2) -> str:
        """Save payload dictionary to JSON file."""
        target_path = Path(filepath)
        target_path.parent.mkdir(parents=True, exist_ok=True)
        with open(target_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=indent)
        return str(target_path)


def setup_collector_cli_args(parser: Any) -> None:
    """Setup CLI arguments for collector sub-feature."""
    parser.add_argument(
        "-s",
        "--symbol",
        type=str,
        default="BTCUSDT",
        help="Simbol kripto (contoh: BTC, ETH, SOL, BTCUSDT). Default: BTCUSDT",
    )
    parser.add_argument(
        "-t",
        "--timeframe",
        type=str,
        default="15m",
        choices=["1m", "3m", "5m", "15m", "30m", "1h", "2h", "4h", "6h", "8h", "12h", "1d", "3d", "1w", "1M"],
        help="Interval candle (contoh: 15m, 1h, 4h, 1d). Default: 15m",
    )
    parser.add_argument(
        "-d",
        "--days",
        type=int,
        default=30,
        help="Periode data historis dalam hari (contoh: 7, 30, 90). Default: 30",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=str,
        default=None,
        help="Path file output JSON kustom (default: data/<symbol>_<timeframe>_<days>d_<timestamp>.json)",
    )
    parser.add_argument(
        "--no-doh",
        action="store_true",
        help="Nonaktifkan DNS-over-HTTPS (gunakan DNS sistem)",
    )
    parser.add_argument(
        "-q",
        "--quiet",
        action="store_true",
        help="Hanya tampilkan path file output tanpa log verbose",
    )


def run_collector_cli(args: Any) -> str:
    """Execute collector CLI workflow."""
    symbol = normalize_symbol(args.symbol)
    timeframe = args.timeframe
    days = args.days

    if not args.output:
        now_ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_dir = Path("data")
        output_path = output_dir / f"{symbol}_{timeframe}_{days}d_{now_ts}.json"
    else:
        output_path = Path(args.output)

    if not args.quiet:
        print(f"\n⚡ Mengambil data Binance Futures untuk {symbol} ({timeframe}, {days} hari)...")

    def progress_callback(msg: str):
        if not args.quiet:
            print(f"  • {msg}")

    collector = BinanceCollector(use_doh=not args.no_doh)
    result = collector.collect(
        symbol=symbol,
        timeframe=timeframe,
        days=days,
        status_cb=progress_callback,
    )

    saved_file = collector.save_json(result, str(output_path))
    file_size_kb = os.path.getsize(saved_file) / 1024

    if not args.quiet:
        meta = result["metadata"]
        stats = meta["summary_stats"]
        print(f"\n✅ Berhasil mengumpulkan data {symbol} ({meta['exchange'].upper()}):")
        print(f"  • Total Candlesticks (OHLCV) : {meta['total_candles']:,}")
        print(f"  • Total Funding Rate Events  : {meta['total_funding_events']:,}")
        print(f"  • Total Open Interest Records: {meta['total_oi_records']:,}")
        print(f"  • Rentang Harga              : ${stats['lowest_price']:,.2f} - ${stats['highest_price']:,.2f}")
        print(f"  • Harga Terakhir             : ${stats['latest_price']:,.2f} ({stats['price_change_pct']:+.2f}%)")
        print(f"\n💾 Tersimpan di: {saved_file} ({file_size_kb:,.1f} KB)\n")
    else:
        print(saved_file)

    return saved_file
