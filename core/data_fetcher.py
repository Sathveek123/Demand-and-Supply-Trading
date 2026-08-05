import ccxt
import time
import pandas as pd
import yfinance as yf
from typing import Optional

class MarketDataFetcher:
    """
    Market Data Fetcher supporting Crypto and Stocks/Indices.
    
    Primary data source: yfinance (Yahoo Finance) — works from India, no geo-restrictions.
    Fallback: CCXT (Bybit) — used only if yfinance fails (e.g. symbol not found).
    Crypto exchange APIs (Binance, Bybit) are ISP-level blocked in India.
    """

    def __init__(self):
        # CCXT kept as fallback only — crypto exchange APIs are blocked by ISPs in India
        try:
            self.exchange = ccxt.bybit({
                'enableRateLimit': True,
                'options': {'defaultType': 'spot'}
            })
        except Exception:
            self.exchange = None

    @staticmethod
    def _symbol_to_yf(symbol: str) -> str:
        """
        Converts asset tickers to yfinance format:
        BTC/USDT -> BTC-USD
        ETH/USDT -> ETH-USD
        XAUUSD / GOLD -> GC=F (Gold Futures)
        EURUSD / EUR/USD -> EURUSD=X
        """
        clean = symbol.upper().replace("-", "").replace("_", "").replace("/", "").strip()
        if clean in ["XAUUSD", "GOLD", "GCF", "GC"]:
            return "GC=F"
        elif clean in ["EURUSD", "EURUSDX"]:
            return "EURUSD=X"
        elif clean.endswith("USDT") and len(clean) > 4:
            base = clean[:-4]
            return f"{base}-USD"
        elif clean.endswith("BUSD") and len(clean) > 4:
            base = clean[:-4]
            return f"{base}-USD"
        elif clean in ["BTC", "ETH", "SOL"]:
            return f"{clean}-USD"
        else:
            if "/" in symbol:
                base = symbol.upper().split("/")[0]
                return f"{base}-USD"
            return f"{clean}-USD"

    def _fetch_yf_candles(self, yf_symbol: str, timeframe: str = "3m", limit: int = 100) -> pd.DataFrame:
        """
        Core yfinance fetcher with retry loop and Ticker fallback to safeguard against Yahoo rate limits.
        Uses period='2d' for intraday timeframes to avoid intermittent Yahoo 'possibly delisted' false-positives.
        """
        import random
        interval_map = {"3m": "2m", "15m": "15m", "5m": "5m", "1m": "1m", "1h": "60m"}
        interval = interval_map.get(timeframe, "2m")
        # Use '2d' for 3M/5M intraday to avoid intermittent Yahoo Finance empty responses
        period = "5d" if timeframe in ["15m", "1h"] else "2d"

        def _flatten_columns(df: pd.DataFrame) -> pd.DataFrame:
            """Robustly flatten MultiIndex columns from yf.download reset_index."""
            if isinstance(df.columns, pd.MultiIndex):
                # After reset_index: ('Datetime','') -> 'datetime', ('Close','BTC-USD') -> 'close'
                flat = []
                for col in df.columns:
                    if isinstance(col, tuple):
                        # col[0] is the price type label
                        label = str(col[0]).lower().strip()
                        flat.append(label)
                    else:
                        flat.append(str(col).lower().strip())
                df.columns = flat
            else:
                df.columns = [str(c).lower().strip() for c in df.columns]
            return df

        for attempt in range(3):
            try:
                time.sleep(random.uniform(0.5, 1.5))
                data = yf.download(tickers=yf_symbol, period=period, interval=interval, progress=False)
                if not data.empty:
                    df = data.reset_index()
                    df = _flatten_columns(df)
                    # Normalize timestamp column name
                    for ts_col in ['datetime', 'date', 'index']:
                        if ts_col in df.columns:
                            df.rename(columns={ts_col: 'timestamp'}, inplace=True)
                            break
                    needed = ['timestamp', 'open', 'high', 'low', 'close', 'volume']
                    if all(c in df.columns for c in needed):
                        df = df[needed].tail(limit).reset_index(drop=True)
                        last_close = float(df['close'].iloc[-1])
                        print(f"[RAW CHECK] {yf_symbol} {timeframe} last close = {last_close:.4f} (via yf.download)")
                        return df
                    else:
                        missing = [c for c in needed if c not in df.columns]
                        print(f"[MarketDataFetcher]: yf.download missing columns {missing} for {yf_symbol}. Retrying...")
            except Exception as e:
                print(f"[MarketDataFetcher]: yf.download attempt {attempt+1} error for {yf_symbol}: {e}")

        # Fallback to Ticker().history() if yf.download intermittent failure occurs
        try:
            time.sleep(1.0)
            ticker_obj = yf.Ticker(yf_symbol)
            data = ticker_obj.history(period=period, interval=interval)
            if not data.empty:
                df = data.reset_index()
                df.columns = [str(c).lower().strip() for c in df.columns]
                for ts_col in ['datetime', 'date', 'index']:
                    if ts_col in df.columns:
                        df.rename(columns={ts_col: 'timestamp'}, inplace=True)
                        break
                needed = ['timestamp', 'open', 'high', 'low', 'close', 'volume']
                if all(c in df.columns for c in needed):
                    df = df[needed].tail(limit).reset_index(drop=True)
                    last_close = float(df['close'].iloc[-1])
                    print(f"[RAW CHECK] {yf_symbol} {timeframe} last close = {last_close:.4f} (via Ticker.history fallback)")
                    return df
        except Exception as e:
            print(f"[MarketDataFetcher]: Ticker.history fallback error for {yf_symbol}: {e}")

        return pd.DataFrame()

    def fetch_crypto_candles(self, symbol: str = "BTC/USDT", timeframe: str = "3m", limit: int = 100) -> pd.DataFrame:
        """
        Fetches OHLCV candle data for Crypto/Forex/Commodity pairs.
        Primary: yfinance (Yahoo Finance) — geo-restriction free, works from India.
        Fallback: CCXT Bybit → Simulated candles.
        """
        yf_symbol = self._symbol_to_yf(symbol)

        df = self._fetch_yf_candles(yf_symbol, timeframe=timeframe, limit=limit)
        if not df.empty:
            return df

        # --- Fallback: CCXT Bybit ---
        if self.exchange is not None:
            try:
                clean_symbol = symbol.upper().replace("-", "/").replace("_", "/")
                if "/" not in clean_symbol:
                    clean_symbol = f"{clean_symbol[:-4]}/USDT" if clean_symbol.endswith("USDT") else clean_symbol
                ohlcv = self.exchange.fetch_ohlcv(clean_symbol, timeframe=timeframe, limit=limit)
                df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
                df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
                print(f"[RAW CHECK] {clean_symbol} {timeframe} last close = {df['close'].iloc[-1]:.4f} (via CCXT Bybit fallback)")
                return df
            except Exception as e:
                print(f"[MarketDataFetcher]: CCXT fallback error for {symbol}: {e}")

        # --- Last Resort: Simulated candles ---
        print(f"[MarketDataFetcher]: All sources failed for {symbol}. Using simulated candles.")
        return self._generate_simulated_candles(symbol=symbol, timeframe=timeframe, limit=limit)

    def fetch_stock_candles(self, ticker: str = "^NSEI", timeframe: str = "3m", limit: int = 100) -> pd.DataFrame:
        """
        Fetches OHLCV candle data for stock indices (Nifty ^NSEI, BankNifty ^NSEBANK) using YFinance.
        """
        yf_ticker = ticker if ticker.startswith("^") else self._symbol_to_yf(ticker)

        df = self._fetch_yf_candles(yf_ticker, timeframe=timeframe, limit=limit)
        if not df.empty:
            return df

        return self._generate_simulated_candles(symbol=ticker, timeframe=timeframe, limit=limit)

    def fetch_live_price(self, symbol: str) -> Optional[float]:
        """
        Fetches the real-time live price of the symbol via yfinance.
        """
        # Try yfinance first for crypto
        try:
            yf_sym = self._symbol_to_yf(symbol)
            ticker = yf.Ticker(yf_sym)
            info = ticker.fast_info
            price = getattr(info, 'last_price', None) or getattr(info, 'regularMarketPrice', None)
            if price and float(price) > 0:
                print(f"[LIVE PRICE] {yf_sym} = {price:.4f} (via yfinance)")
                return float(price)
        except Exception as e:
            print(f"[MarketDataFetcher]: yfinance live price error for {symbol}: {e}")

        # Fallback: CCXT Bybit
        if self.exchange is not None:
            try:
                clean_symbol = symbol.upper().replace("-", "/").replace("_", "/")
                ticker_data = self.exchange.fetch_ticker(clean_symbol)
                return float(ticker_data["last"])
            except Exception as e:
                print(f"[MarketDataFetcher]: CCXT live price fallback error for {symbol}: {e}")

        return None

    def _generate_simulated_candles(self, symbol: str = "BTC/USDT", timeframe: str = "3m", limit: int = 100) -> pd.DataFrame:
        """
        Generates clean unique simulated candle data if ALL live market APIs are unavailable.
        Uses timeframe-specific random state offset to avoid copy-paste matching variables.
        Prices reflect current real-world approximate values (updated Aug 2024).
        """
        import numpy as np
        dates = pd.date_range(end=pd.Timestamp.now(), periods=limit, freq="3min" if timeframe == "3m" else "15min")

        # Unique seed per timeframe to ensure independent variables
        tf_seed = int(sum(ord(c) for c in timeframe)) + int(time.time() * 100) % 1000
        np.random.seed(tf_seed)

        # Real approximate prices
        symbol_upper = symbol.upper() if symbol else ""
        if "BTC" in symbol_upper:
            base_price = 59000.0
        elif "ETH" in symbol_upper:
            base_price = 1560.0
        elif "SOL" in symbol_upper:
            base_price = 73.0
        elif "XAU" in symbol_upper or "GOLD" in symbol_upper:
            base_price = 2400.0
        elif "EUR" in symbol_upper:
            base_price = 1.08
        elif "NSEI" in symbol_upper or "NIFTY" in symbol_upper:
            base_price = 24500.0
        else:
            base_price = 100.0

        price = base_price
        prices = [price]

        for _ in range(limit - 1):
            prices.append(prices[-1] + np.random.normal(0, base_price * 0.001))

        df = pd.DataFrame({
            'timestamp': dates,
            'open': prices,
            'high': [p + abs(np.random.normal(0, base_price * 0.0005)) for p in prices],
            'low': [p - abs(np.random.normal(0, base_price * 0.0005)) for p in prices],
            'close': [p + np.random.normal(0, base_price * 0.0003) for p in prices],
            'volume': np.random.randint(100, 1000, size=limit)
        })
        return df
