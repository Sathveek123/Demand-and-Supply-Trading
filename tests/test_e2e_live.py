"""
Full end-to-end live validation — all 4 assets.
Tests: data fetcher → SMC engine → signal formatter → output
"""
import sys, os
import io

# Force UTF-8 output — Windows defaults to cp1252 which crashes on emoji in print statements
if sys.stdout.encoding != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
if sys.stderr.encoding != 'utf-8':
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import time
from core.data_fetcher import MarketDataFetcher
from core.smc_engine import SMCEngine
from core.llm_signal import SignalFormatter

fetcher = MarketDataFetcher()
ASSETS = ["BTC/USDT", "ETH/USDT", "XAUUSD", "EURUSD"]

print("=" * 60)
print("  FULL END-TO-END VALIDATION — ALL 4 ASSETS")
print("=" * 60)

all_ok = True

for asset in ASSETS:
    print(f"\n{'-'*50}")
    print(f"  ASSET: {asset}")
    print(f"{'-'*50}")
    
    try:
        # Step 1: Fetch candles
        df_15m = fetcher.fetch_crypto_candles(symbol=asset, timeframe="15m", limit=100)
        time.sleep(1.5)
        df_3m = fetcher.fetch_crypto_candles(symbol=asset, timeframe="3m", limit=100)
        
        # Step 2: Live price
        live_price = fetcher.fetch_live_price(asset)
        print(f"  Live price: {live_price}")
        
        # Step 3: Check data quality
        if df_15m.empty:
            print(f"  ❌ 15M data EMPTY")
            all_ok = False
            continue
        if df_3m.empty:
            print(f"  ❌ 3M data EMPTY")
            all_ok = False
            continue

        print(f"  ✅ 15M candles: {len(df_15m)} rows  |  last close: {df_15m['close'].iloc[-1]:.4f}")
        print(f"  ✅ 3M candles : {len(df_3m)} rows  |  last close: {df_3m['close'].iloc[-1]:.4f}")
        
        # Step 4: Run SMC analysis
        analysis = SMCEngine.analyze_setup(
            asset_name=asset,
            df_15m=df_15m,
            df_3m=df_3m,
            live_price=live_price
        )
        
        valid = analysis.get("valid", False)
        reason = analysis.get("reason", "")
        print(f"  {'✅' if valid else '⏳'} SMC Result: valid={valid}  reason={reason[:60] if reason else 'SIGNAL FOUND'}")
        
        if valid:
            entry = analysis.get("entry", 0)
            sl = analysis.get("stop_loss", 0)
            tp1 = analysis.get("tp1", 0)
            tp2 = analysis.get("tp2", 0)
            print(f"     Entry={entry}  SL={sl}  TP1={tp1}  TP2={tp2}")
            # Validate TP math
            risk = abs(entry - sl)
            if risk > 0:
                expected_tp1 = entry + risk if analysis.get("signal_type") == "BUY" else entry - risk
                expected_tp2 = entry + 2*risk if analysis.get("signal_type") == "BUY" else entry - 2*risk
                tp1_ok = abs(tp1 - expected_tp1) < 0.01 * risk
                tp2_ok = abs(tp2 - expected_tp2) < 0.01 * risk
                print(f"     TP1 math: {'✅' if tp1_ok else '❌'}  TP2 math: {'✅' if tp2_ok else '❌'}")
                if not (tp1_ok and tp2_ok):
                    all_ok = False
        
        # Step 5: Format signal
        formatted = SignalFormatter.format_signal(analysis)
        if "NULL_SIGNAL" in formatted:
            print(f"  ❌ Formatter returned NULL_SIGNAL: {formatted}")
            all_ok = False
        else:
            preview = formatted[:80].replace('\n', ' | ')
            print(f"  ✅ Formatter: {preview}...")
        
        time.sleep(2.0)
        
    except Exception as e:
        print(f"  ❌ EXCEPTION: {e}")
        import traceback
        traceback.print_exc()
        all_ok = False

print("\n" + "=" * 60)
if all_ok:
    print("  ✅ ALL VALIDATIONS PASSED")
else:
    print("  ⚠️  SOME CHECKS HAD ISSUES (see above)")
print("=" * 60)
