"""
Unit tests for FastAPI Web Server endpoints using requests.
"""

import json
import unittest
import requests

SERVER_URL = "http://127.0.0.1:8000"


class TestWebServer(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            res = requests.get(f"{SERVER_URL}/api/health", timeout=2)
            cls.server_online = (res.status_code == 200)
        except Exception:
            cls.server_online = False

    def setUp(self):
        if not self.server_online:
            self.skipTest("Local web server is not running on port 8000")

    def test_health_check(self):
        res = requests.get(f"{SERVER_URL}/api/health", timeout=3)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["status"], "healthy")
        self.assertEqual(data["engine"], "CryptoForecastEngine")

    def test_presets_list(self):
        res = requests.get(f"{SERVER_URL}/api/presets", timeout=3)
        self.assertEqual(res.status_code, 200)
        presets = res.json()
        self.assertIsInstance(presets, list)
        filenames = [p["filename"] for p in presets]
        self.assertIn("ETHUSDT_15m_1d.json", filenames)

    def test_forecast_preset_endpoint(self):
        res = requests.get(
            f"{SERVER_URL}/api/forecast/preset/ETHUSDT_15m_1d.json?horizon=16&mc_sims=1000",
            timeout=5
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["metadata"]["symbol"], "ETHUSDT")
        self.assertEqual(len(data["forecast_data"]), 16)
        self.assertIn("M6_Best_Ensemble", data["backtest_metrics"])
        self.assertIn("M1_Holt_Damped", data["ensemble_weights"])
        self.assertIn("spot_order_recommendation", data)

    def test_simulate_barriers_endpoint(self):
        payload = {
            "current_price": 2269.0,
            "ensemble_path": [2270.0, 2272.0, 2275.0],
            "ci_80_upper": [2280.0, 2285.0, 2290.0],
            "upside_barriers": [2300.0],
            "downside_barriers": [2200.0],
            "step_minutes": 15,
            "mc_simulations": 1000,
            "student_df": 6,
        }
        res = requests.post(f"{SERVER_URL}/api/barriers/simulate", json=payload, timeout=3)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("2300.0", data["upside"])
        self.assertIn("touch_24h_pct", data["upside"]["2300.0"])

    def test_binance_download_endpoint(self):
        res = requests.get(
            f"{SERVER_URL}/api/binance/download?symbol=ETHUSDT&timeframe=15m&days=1&save_server=false",
            timeout=8,
        )
        self.assertEqual(res.status_code, 200)
        filename = res.headers.get("X-Dataset-Filename", "")
        self.assertTrue(filename.startswith("ETHUSDT_15m_1d_"))
        self.assertTrue(filename.endswith(".json"))
        # Check that timestamp portion is 15 characters (YYYYMMDD_HHMMSS)
        ts_part = filename.replace("ETHUSDT_15m_1d_", "").replace(".json", "")
        self.assertEqual(len(ts_part), 15)
        self.assertIn("_", ts_part)
        data = res.json()
        self.assertIn("metadata", data)
        self.assertIn("data", data)
        self.assertGreaterEqual(len(data["data"]), 90)

    def test_forecast_replay_endpoint(self):
        res = requests.get(
            f"{SERVER_URL}/api/forecast/replay/ETHUSDT_15m_1d.json?back=16&mc_sims=1000",
            timeout=8,
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("summary", data)
        self.assertIn("comparison_steps", data)
        self.assertEqual(len(data["comparison_steps"]), 16)
        self.assertEqual(data["summary"]["back_candles"], 16)
        self.assertIn("spot_order_recommendation", data)


if __name__ == "__main__":
    unittest.main()
