import unittest
import pandas as pd
import numpy as np
from core.smc_engine import SMCEngine
from core.llm_signal import SignalFormatter

class TestSMCEngine(unittest.TestCase):

    def setUp(self):
        # Create synthetic 15M Bullish data
        dates_15m = pd.date_range(end=pd.Timestamp.now(), periods=50, freq="15min")
        prices_15m = np.linspace(100, 200, 50) + np.random.normal(0, 2, 50)
        self.df_15m = pd.DataFrame({
            'timestamp': dates_15m,
            'open': prices_15m - 1,
            'high': prices_15m + 3,
            'low': prices_15m - 2,
            'close': prices_15m,
            'volume': 1000
        })

        # Create synthetic 3M data with Bullish OB & Engulfing confirmation
        dates_3m = pd.date_range(end=pd.Timestamp.now(), periods=30, freq="3min")
        prices_3m = [150.0] * 30
        
        df_3m = pd.DataFrame({
            'timestamp': dates_3m,
            'open': prices_3m,
            'high': [p + 2 for p in prices_3m],
            'low': [p - 2 for p in prices_3m],
            'close': prices_3m,
            'volume': 500
        })

        # Inject Bullish OB at index 10 (Red candle followed by strong green expansion)
        df_3m.loc[10, ['open', 'high', 'low', 'close']] = [152.0, 153.0, 148.0, 149.0] # Red OB
        df_3m.loc[11, ['open', 'high', 'low', 'close']] = [149.0, 157.0, 149.0, 156.0] # Green impulse
        df_3m.loc[12, ['open', 'high', 'low', 'close']] = [156.0, 162.0, 156.0, 161.0] # Expansion

        # Inject Confirmation candle at end (Bullish Engulfing near OB)
        df_3m.loc[28, ['open', 'high', 'low', 'close']] = [151.0, 152.0, 148.5, 149.5] # Red pullback
        df_3m.loc[29, ['open', 'high', 'low', 'close']] = [149.5, 155.0, 149.0, 154.0] # Green Engulfing confirmation

        self.df_3m = df_3m

    def test_trend_detection(self):
        trend, method = SMCEngine.detect_15m_trend(self.df_15m)
        self.assertIn(trend, ["BULLISH", "BEARISH", "SIDEWAYS"])

    def test_smc_analysis(self):
        result = SMCEngine.analyze_setup("TEST_ASSET", self.df_15m, self.df_3m)
        self.assertIn("valid", result)
        if result["valid"]:
            self.assertEqual(result["signal_type"], "BUY")
            self.assertGreater(result["tp1"], result["entry"])
            self.assertGreater(result["tp2"], result["tp1"])
            self.assertLess(result["stop_loss"], result["entry"])

    def test_telegram_signal_format(self):
        sample_data = {
            "valid": True,
            "signal_type": "BUY",
            "asset": "BTC/USDT",
            "trend_15m": "Bullish",
            "setup": "Order Block + FVG on 3M",
            "confirmation": "Bullish Engulfing at OB Zone",
            "entry": 65000.0,
            "stop_loss": 64800.0,
            "tp1": 65200.0,
            "tp2": 65400.0,
            "estimated_hold": "15–40 min",
            "confidence": "🔥 HIGH"
        }

        output = SignalFormatter.format_signal(sample_data)
        self.assertIn("🟢 BUY  •  BTC/USDT", output)
        self.assertIn("✅ Trend (15M)  : Bullish", output)
        self.assertIn("🎯 Entry  →  65,000", output)
        self.assertIn("💰 TP1    →  65,200  (1:1 RR)", output)
        self.assertIn("💰 TP2    →  65,400  (1:2 RR)", output)

if __name__ == "__main__":
    unittest.main()
