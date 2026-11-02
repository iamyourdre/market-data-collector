"""
Unit and Integration Tests for Binance Market Data Collector Sub-feature.
"""

import unittest
from datetime import datetime, timezone

from src.collector import BinanceCollector, normalize_symbol, resolve_doh


class TestBinanceCollector(unittest.TestCase):

    def test_symbol_normalization(self):
        self.assertEqual(normalize_symbol("btc"), "BTCUSDT")
        self.assertEqual(normalize_symbol("ETH/USDT"), "ETHUSDT")
        self.assertEqual(normalize_symbol("sol-usdt"), "SOLUSDT")
        self.assertEqual(normalize_symbol("DOGE"), "DOGEUSDT")
        self.assertEqual(normalize_symbol("BTCUSD"), "BTCUSD")

    def test_doh_resolution(self):
        ips = resolve_doh("fapi.binance.com")
        self.assertIsInstance(ips, list)
        self.assertGreater(len(ips), 0, "DoH should return at least 1 IP address for fapi.binance.com")

    def test_merge_derivatives(self):
        collector = BinanceCollector(use_doh=False)

        candles = [
            {
                "timestamp": 1000,
                "close_time": 1999,
                "open": 100.0,
                "high": 105.0,
                "low": 99.0,
                "close": 102.0,
                "volume": 10.0,
            },
            {
                "timestamp": 2000,
                "close_time": 2999,
                "open": 102.0,
                "high": 108.0,
                "low": 101.0,
                "close": 106.0,
                "volume": 12.0,
            },
        ]

        funding_rates = [
            {"timestamp": 500, "funding_rate": 0.0001, "mark_price": 100.0},
            {"timestamp": 2500, "funding_rate": 0.0002, "mark_price": 105.0},
        ]

        open_interests = [
            {"timestamp": 1200, "open_interest": 500.0, "open_interest_usd": 50000.0},
            {"timestamp": 2200, "open_interest": 600.0, "open_interest_usd": 63600.0},
        ]

        merged = collector.merge_derivatives(candles, funding_rates, open_interests)

        # Candle 0 checks
        self.assertEqual(merged[0]["funding_rate"], 0.0001)
        self.assertIsNone(merged[0]["funding_settled"])
        self.assertEqual(merged[0]["open_interest"], 500.0)

        # Candle 1 checks (funding settlement happened at 2500, inside [2000, 2999])
        self.assertEqual(merged[1]["funding_settled"], 0.0002)
        self.assertEqual(merged[1]["open_interest"], 600.0)

    def test_live_binance_quick_collection(self):
        """Fetch 1 day of BTC 1h data to ensure live Binance API connectivity."""
        collector = BinanceCollector()
        result = collector.collect(symbol="BTC", timeframe="1h", days=1)

        self.assertIn("metadata", result)
        self.assertIn("data", result)
        self.assertEqual(result["metadata"]["symbol"], "BTCUSDT")
        self.assertGreaterEqual(result["metadata"]["total_candles"], 20)

        first_candle = result["data"][0]
        self.assertIn("open", first_candle)
        self.assertIn("close", first_candle)
        self.assertIn("volume", first_candle)
        self.assertIn("open_interest", first_candle)
        self.assertIn("funding_rate", first_candle)


if __name__ == "__main__":
    unittest.main()
