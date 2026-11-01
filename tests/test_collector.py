"""
Unit and Integration Tests for Crypto Market Data Collector.
"""

import unittest
import numpy as np
import pandas as pd

from src.config import CollectorConfig, normalize_symbol
from src.indicators.calculator import calculate_rsi, calculate_macd, calculate_ema, compute_all_indicators
from src.collectors.binance import BinanceFuturesCollector
from src.collectors.bybit import BybitFuturesCollector
from src.network.doh import enable_doh


class TestMarketDataCollector(unittest.TestCase):

    def setUp(self):
        enable_doh()

    def test_symbol_normalization(self):
        self.assertEqual(normalize_symbol("btc"), "BTCUSDT")
        self.assertEqual(normalize_symbol("ETH/USDT"), "ETHUSDT")
        self.assertEqual(normalize_symbol("sol-usdt"), "SOLUSDT")
        self.assertEqual(normalize_symbol("DOGE"), "DOGEUSDT")
        self.assertEqual(normalize_symbol("BTCUSD"), "BTCUSD")

    def test_rsi_bounds_and_validity(self):
        # Generate monotonic uptrend and downtrend
        uptrend = pd.Series([100.0 + i * 2.0 for i in range(50)])
        rsi_up = calculate_rsi(uptrend, period=14)
        self.assertTrue((rsi_up.dropna() >= 0).all() and (rsi_up.dropna() <= 100).all())
        # In strong continuous uptrend, RSI should be high (>70)
        self.assertGreater(rsi_up.iloc[-1], 70.0)

        downtrend = pd.Series([200.0 - i * 2.0 for i in range(50)])
        rsi_down = calculate_rsi(downtrend, period=14)
        self.assertTrue((rsi_down.dropna() >= 0).all() and (rsi_down.dropna() <= 100).all())
        # In strong continuous downtrend, RSI should be low (<30)
        self.assertLess(rsi_down.iloc[-1], 30.0)

    def test_macd_calculation(self):
        prices = pd.Series([100 + (i % 10) * 2 for i in range(60)], dtype=float)
        macd_df = calculate_macd(prices, fast=12, slow=26, signal=9)
        self.assertIn("macd", macd_df.columns)
        self.assertIn("macd_signal", macd_df.columns)
        self.assertIn("macd_hist", macd_df.columns)
        # Verify hist = macd - signal
        diff = macd_df["macd"] - macd_df["macd_signal"]
        np.testing.assert_allclose(macd_df["macd_hist"].values, diff.values)

    def test_ema_calculation(self):
        prices = pd.Series([50.0 + i for i in range(250)], dtype=float)
        ema_df = calculate_ema(prices, periods=[20, 50, 200])
        self.assertIn("ema_20", ema_df.columns)
        self.assertIn("ema_50", ema_df.columns)
        self.assertIn("ema_200", ema_df.columns)
        # In steady uptrend, EMA 20 > EMA 50 > EMA 200
        self.assertGreater(ema_df["ema_20"].iloc[-1], ema_df["ema_50"].iloc[-1])
        self.assertGreater(ema_df["ema_50"].iloc[-1], ema_df["ema_200"].iloc[-1])

    def test_live_binance_collector_quick(self):
        """Test live collection of a short 2-day period to verify API connectivity and merge."""
        collector = BinanceFuturesCollector()
        cfg = CollectorConfig(
            symbol="BTCUSDT",
            timeframe="1d",
            days=3,
            source="binance",
            warmup_candles=5,
        )
        result = collector.collect(cfg)
        self.assertFalse(result.df_merged.empty)
        self.assertIn("close", result.df_merged.columns)
        self.assertIn("rsi_14", result.df_merged.columns)
        self.assertIn("macd_line", result.df_merged.columns)
        self.assertIn("ema_20", result.df_merged.columns)
        self.assertGreaterEqual(len(result.df_merged), 2)
        print(f"\nBinance quick test collected {len(result.df_merged)} daily candles successfully.")

    def test_live_bybit_collector_quick(self):
        """Test live Bybit collection for a short 2-day period."""
        collector = BybitFuturesCollector()
        cfg = CollectorConfig(
            symbol="ETHUSDT",
            timeframe="1d",
            days=3,
            source="bybit",
            warmup_candles=5,
        )
        result = collector.collect(cfg)
        self.assertFalse(result.df_merged.empty)
        self.assertIn("close", result.df_merged.columns)
        self.assertIn("rsi_14", result.df_merged.columns)
        self.assertGreaterEqual(len(result.df_merged), 2)
        print(f"\nBybit quick test collected {len(result.df_merged)} daily candles successfully.")


if __name__ == "__main__":
    unittest.main()
