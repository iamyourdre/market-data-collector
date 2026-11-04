"""
Unit tests for CryptoForecastEngine and quantitative forecasting pipeline.
"""

import json
import unittest
from pathlib import Path
import numpy as np
import pandas as pd

from crypto_forecast_engine import (
    CryptoForecastEngine,
    ForecastConfig,
    run_forecast_pipeline,
    run_replay_pipeline,
)

BASE_DIR = Path(__file__).resolve().parent.parent
ETH_JSON_PATH = BASE_DIR / "data" / "ETHUSDT_15m_1d.json"
BTC_JSON_PATH = BASE_DIR / "data" / "BTCUSDT_1h_2d.json"


class TestCryptoForecastEngine(unittest.TestCase):
    def test_eth_data_ingestion_and_indicators(self):
        """Test that ETHUSDT_15m_1d.json loads and missing indicators are computed."""
        engine = CryptoForecastEngine()
        df = engine.load_json(str(ETH_JSON_PATH))

        self.assertIsInstance(df, pd.DataFrame)
        self.assertEqual(len(df), 96)
        self.assertEqual(engine.step_minutes, 15)

        # Check required columns
        for col in ["open", "high", "low", "close", "volume", "rsi_14", "ema_20", "ema_50", "ema_200", "macd_hist"]:
            self.assertIn(col, df.columns)
            self.assertFalse(df[col].isna().all(), f"Column {col} has all NaNs")

        # Spot price should match JSON
        self.assertEqual(float(df["close"].iloc[-1]), 2269.0)

    def test_feature_engineering(self):
        """Test that all 18 exogenous features are built without NaNs or Infs."""
        engine = CryptoForecastEngine()
        engine.load_json(str(ETH_JSON_PATH))
        df_feat = engine.build_features()

        for col in CryptoForecastEngine.FEATURE_COLS:
            self.assertIn(col, df_feat.columns)
            self.assertFalse(df_feat[col].isna().any(), f"Column {col} contains NaN")
            self.assertFalse(np.isinf(df_feat[col]).any(), f"Column {col} contains Inf")

    def test_walk_forward_and_forecast_generation(self):
        """Test walk-forward evaluation and 24-step forecast generation."""
        cfg = ForecastConfig(horizon_steps=24, mc_simulations=1000)
        engine = CryptoForecastEngine(cfg)
        engine.load_json(str(ETH_JSON_PATH))
        engine.build_features()

        metrics = engine.run_walk_forward_backtest()
        self.assertIn("M6_Best_Ensemble", metrics)
        self.assertGreater(len(engine.ensemble_weights), 0)

        weights_sum = sum(engine.ensemble_weights.values())
        self.assertAlmostEqual(weights_sum, 1.0, places=2)

        df_fc = engine.generate_forecasts()
        self.assertEqual(len(df_fc), 24)
        for col in ["M6_Best_Ensemble", "ci_50_lower", "ci_50_upper", "ci_80_lower", "ci_80_upper"]:
            self.assertIn(col, df_fc.columns)

        # Check monotonic confidence cones
        self.assertTrue((df_fc["ci_50_lower"] <= df_fc["M6_Best_Ensemble"]).all())
        self.assertTrue((df_fc["M6_Best_Ensemble"] <= df_fc["ci_50_upper"]).all())
        self.assertTrue((df_fc["ci_80_lower"] <= df_fc["ci_50_lower"]).all())
        self.assertTrue((df_fc["ci_50_upper"] <= df_fc["ci_80_upper"]).all())

    def test_run_forecast_pipeline_helper(self):
        """Test high-level run_forecast_pipeline function."""
        result = run_forecast_pipeline(
            source=str(ETH_JSON_PATH),
            horizon_steps=16,
            mc_simulations=1000,
        )
        self.assertIn("metadata", result)
        self.assertIn("historical_data", result)
        self.assertIn("forecast_data", result)
        self.assertIn("summary", result)
        self.assertIn("barrier_probabilities", result)

        self.assertEqual(len(result["historical_data"]), 96)
        self.assertEqual(len(result["forecast_data"]), 16)
        self.assertIn(result["summary"]["direction"], ["BULLISH", "BEARISH", "NEUTRAL"])

    def test_btc_hourly_compatibility(self):
        """Test compatibility with BTCUSDT 1h 2d dataset."""
        result = run_forecast_pipeline(
            source=str(BTC_JSON_PATH),
            horizon_steps=12,
            mc_simulations=1000,
        )
        self.assertEqual(result["metadata"]["symbol"], "BTCUSDT")
        self.assertEqual(result["metadata"]["step_minutes"], 60)
        self.assertEqual(len(result["historical_data"]), 48)
        self.assertEqual(len(result["forecast_data"]), 12)

    def test_replay_pipeline_execution(self):
        """Test out-of-sample replay pipeline with customizable back candles."""
        result = run_replay_pipeline(
            source=str(ETH_JSON_PATH),
            back_candles=16,
            mc_simulations=1000,
        )
        self.assertIn("summary", result)
        self.assertIn("comparison_steps", result)
        self.assertIn("actual_forward_data", result)
        self.assertEqual(len(result["comparison_steps"]), 16)
        self.assertEqual(result["summary"]["back_candles"], 16)
        self.assertIn("rmse", result["summary"])
        self.assertIn("direction_match", result["summary"])
        self.assertIsInstance(result["summary"]["direction_match"], bool)


if __name__ == "__main__":
    unittest.main()
