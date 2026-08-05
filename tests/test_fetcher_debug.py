import yfinance as yf
import pandas as pd

# Test BTC with different periods
for period in ['5d', '2d', '1d']:
    try:
        data = yf.download(tickers='BTC-USD', period=period, interval='2m', progress=False)
        print(f"BTC-USD period={period} interval=2m: shape={data.shape}, empty={data.empty}")
    except Exception as e:
        print(f"BTC-USD period={period}: ERROR {e}")

for period in ['5d', '7d']:
    try:
        data = yf.download(tickers='BTC-USD', period=period, interval='15m', progress=False)
        print(f"BTC-USD period={period} interval=15m: shape={data.shape}, empty={data.empty}")
    except Exception as e:
        print(f"BTC-USD period={period} 15m: ERROR {e}")

# Also try Ticker directly
print("\n--- Ticker.history fallback ---")
t = yf.Ticker('BTC-USD')
h = t.history(period='1d', interval='2m')
print(f"Ticker.history 1d/2m: shape={h.shape}, empty={h.empty}")
h5 = t.history(period='5d', interval='15m')
print(f"Ticker.history 5d/15m: shape={h5.shape}, empty={h5.empty}")
