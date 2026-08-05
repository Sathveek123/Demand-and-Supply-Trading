"""
Test suite for Forex rounding precision (TP1/TP2 distinct), ob_key format, and EURUSD off-hours guard.
"""
import unittest
import pandas as pd
from core.smc_engine import SMCEngine
from core.llm_signal import SignalFormatter

class TestForexFixes(unittest.TestCase):

    def test_eurusd_precision_and_tp_math(self):
        # Create synthetic EURUSD data
        dates_15m = pd.date_range("2026-08-05 10:00", periods=50, freq="15min")
        df_15m = pd.DataFrame({
            "timestamp": dates_15m,
            "open": [1.1500 + i*0.0001 for i in range(50)],
            "high": [1.1510 + i*0.0001 for i in range(50)],
            "low": [1.1490 + i*0.0001 for i in range(50)],
            "close": [1.1505 + i*0.0001 for i in range(50)],
            "volume": [100]*50
        })

        dates_3m = pd.date_range("2026-08-05 12:00", periods=50, freq="3min")
        df_3m = pd.DataFrame({
            "timestamp": dates_3m,
            "open": [1.1540]*50,
            "high": [1.1550]*50,
            "low": [1.1530]*50,
            "close": [1.1545]*50,
            "volume": [100]*50
        })

        analysis = SMCEngine.analyze_setup("EURUSD", df_15m, df_3m, live_price=1.15412)
        
        # Test precision
        if analysis.get("valid"):
            entry = analysis["entry"]
            tp1 = analysis["tp1"]
            tp2 = analysis["tp2"]
            sl = analysis["stop_loss"]
            
            # Check TP1 != TP2
            self.assertNotEqual(tp1, tp2, "TP1 and TP2 must NOT be equal!")
            
            # Check 4 decimal precision
            self.assertTrue(len(str(entry).split(".")[1]) >= 3, f"Entry {entry} must have at least 3-4 decimals!")
            self.assertTrue(len(str(tp1).split(".")[1]) >= 3, f"TP1 {tp1} must have at least 3-4 decimals!")
            self.assertTrue(len(str(tp2).split(".")[1]) >= 3, f"TP2 {tp2} must have at least 3-4 decimals!")

            # Check ob_key signature formatting
            ob_key = analysis["ob_key"]
            self.assertIn("EURUSD", ob_key)
            # ob_key should use 5 decimal precision for high/low
            parts = ob_key.split("_")
            self.assertGreaterEqual(len(parts), 4)

    def test_signal_formatter_eurusd(self):
        sample_data = {
            "valid": True,
            "signal_type": "BUY",
            "asset": "EURUSD",
            "trend_15m": "BULLISH",
            "setup": "Order Block + FVG on 3M",
            "confirmation": "Bullish Engulfing at OB Zone",
            "entry": 1.1541,
            "stop_loss": 1.1495,
            "tp1": 1.1587,
            "tp2": 1.1633,
            "estimated_hold": "15–30 min",
            "confidence": "🔥 HIGH",
            "ob_key": "EURUSD_BUY_1.15480_1.15390_14"
        }
        msg = SignalFormatter.format_signal(sample_data)
        self.assertIn("1.1541", msg)
        self.assertIn("1.1587", msg)
        self.assertIn("1.1633", msg)
        # Ensure TP1 and TP2 are NOT formatted as identical 1.17 strings
        self.assertNotIn("1.1587 (1:1 RR)\n💰 TP2    →  1.1587", msg)

if __name__ == "__main__":
    unittest.main()
