# SMC Pullback Trading Bot — 100% Complete Project Documentation

> **Every file. Every function. Every decision. Every bug. Everything.**
> Last updated: 03-08-2026 | Version: 2.1 (Live)

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [Architecture Diagram](#2-architecture-diagram)
3. [Setup & Installation](#3-setup--installation)
4. [Full File Reference](#4-full-file-reference)
   - [app.py](#41-apppy--fastapi-server--entry-point)
   - [config.py](#42-configpy--settings)
   - [core/smc_engine.py](#43-coresmcenginepy--strategy-brain)
   - [core/data_fetcher.py](#44-coredata_fetcherpy--market-data)
   - [core/scheduler.py](#45-coreschedulerpy--background-scheduler)
   - [core/llm_signal.py](#46-corellm_signalpy--signal-formatter)
   - [bot/telegram_bot.py](#47-bottelegram_botpy--signal-sender)
   - [bot/telegram_listener.py](#48-bottelegram_listenerpy--command-handler)
   - [tests/test_smc_engine.py](#49-teststest_smc_enginepy--unit-tests)
   - [.env / .env.example](#410-env--envexample--environment-config)
5. [Signal Logic — How Entries, SL & TP Are Calculated](#5-signal-logic--how-entries-sl--tp-are-calculated)
6. [Timeframe Logic — How 15M + 3M Work Together](#6-timeframe-logic--how-15m--3m-work-together)
7. [Data Flow — End to End](#7-data-flow--end-to-end)
8. [Telegram Commands Reference](#8-telegram-commands-reference)
9. [Complete Bug Fix Changelog](#9-complete-bug-fix-changelog)
10. [Known Limitations & Future Work](#10-known-limitations--future-work)

---

## 1. Project Overview

**Name:** SMC Pullback Strategy Engine v2.1  
**Type:** Automated cryptocurrency trading signal bot  
**Language:** Python 3.12  
**Status:** Live ✅

### What It Does
- Continuously monitors **BTC/USDT, ETH/USDT, SOL/USDT** every 3 minutes
- Applies **Smart Money Concepts (SMC)** strategy: detects institutional Order Blocks and Fair Value Gaps
- Only fires signals when the 15M trend, 3M OB, FVG confluence, AND a confirmation candle all align
- Sends formatted trade signals to Telegram automatically
- Responds to interactive `/scan`, `/debug`, `/watchlist` commands via Telegram

### Tech Stack

| Component | Technology |
|---|---|
| Web Server | FastAPI + Uvicorn |
| Scheduler | APScheduler + threading |
| Market Data | yfinance (Yahoo Finance) |
| Exchange Fallback | CCXT (Bybit) |
| Signal Formatting | Google Gemini 2.0 Flash + template fallback |
| Telegram | python-telegram-bot v20 + direct HTTP (requests) |
| Config | pydantic-settings + .env |
| Tests | unittest |

---

## 2. Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                        app.py (FastAPI)                         │
│                                                                 │
│  ┌──────────────────┐    ┌──────────────────────────────────┐  │
│  │   /api/scan      │    │   /api/webhook/tradingview       │  │
│  │   ?asset=X       │    │   POST {asset, action}           │  │
│  └────────┬─────────┘    └──────────────┬───────────────────┘  │
│           │                             │                       │
│           └──────────────┬──────────────┘                       │
│                          ▼                                      │
│              scan_asset(asset) function                         │
└──────────────────────────┬──────────────────────────────────────┘
                           │
          ┌────────────────┼────────────────┐
          ▼                ▼                ▼
  ┌───────────────┐ ┌─────────────┐ ┌──────────────────┐
  │ data_fetcher  │ │ smc_engine  │ │  llm_signal      │
  │               │ │             │ │                  │
  │ yfinance      │ │ 1. 15M trend│ │ Gemini 2.0 Flash │
  │ Ticker.history│ │ 2. 3M OBs   │ │      ↓ (fallback)│
  │ (BTC-USD etc) │ │ 3. 3M FVGs  │ │ Template Builder │
  │               │ │ 4. Confluence│ │                  │
  │ Fallback:     │ │ 5. Confirm  │ │ → formatted msg  │
  │ CCXT Bybit    │ │ 6. SL/TP    │ │                  │
  └───────┬───────┘ └──────┬──────┘ └────────┬─────────┘
          │                │                  │
          └────────────────┼──────────────────┘
                           ▼
                ┌────────────────────┐
                │   telegram_bot.py  │
                │                   │
                │  HTTP POST to      │
                │  Telegram API      │
                │  (no parse_mode)   │
                └────────────────────┘

Background Threads (started in app.py startup):
┌─────────────────────────┐    ┌──────────────────────────────┐
│    scheduler.py          │    │    telegram_listener.py      │
│                         │    │                              │
│ Aligns to 3M boundary   │    │ Polling loop                 │
│ → scans BTC/ETH/SOL     │    │ /scan, /debug, /watchlist    │
│   every candle close    │    │ Keyboard buttons             │
│                         │    │ Auto-reconnect on failure    │
└─────────────────────────┘    └──────────────────────────────┘
```

---

## 3. Setup & Installation

### Prerequisites
- Python 3.12+
- A Telegram Bot Token (from [@BotFather](https://t.me/BotFather))
- Your Telegram Chat ID(s)
- (Optional) Google Gemini API Key for AI-formatted signals

### Step 1 — Clone & Install
```bash
cd "d:\Trading bots\Demand Supply Trading bot"
pip install -r requirements.txt
```

### Step 2 — Configure Environment
```bash
copy .env.example .env
```

Edit `.env`:
```env
TELEGRAM_BOT_TOKEN=your_bot_token_from_botfather
TELEGRAM_CHAT_IDS=your_chat_id_here        # Get from @userinfobot
GEMINI_API_KEY=your_gemini_api_key         # Optional — free tier available
USE_LLM_FORMATTER=True
HOST=0.0.0.0
PORT=8000
```

### Step 3 — Run
```bash
python app.py
```

### Step 4 — Verify
Open Telegram → tap `/start` → you should see the welcome message with keyboard buttons.

### Running Tests
```bash
python -m unittest tests/test_smc_engine.py -v
```

---

## 4. Full File Reference

---

### 4.1 `app.py` — FastAPI Server & Entry Point

**Path:** `d:\Trading bots\Demand Supply Trading bot\app.py`  
**Size:** ~160 lines  
**Role:** Entry point. Wires all components together, exposes HTTP endpoints, starts background threads.

#### Startup Sequence
```python
@app.on_event("startup")
def startup_event():
    scheduler.start()                          # Background scan loop (Thread 1)
    threading.Thread(target=run_telegram_listener, daemon=True).start()  # (Thread 2)
```

#### Module-Level State
```python
latest_signals: Dict[str, Any] = {}      # Cache of last scan result per asset
last_sent_signals: Dict[str, Any] = {}   # OB key per asset — duplicate guard
```

#### Endpoints

**`GET /`** — Health check
```json
{
  "status": "online",
  "bot": "SMC Pullback Strategy Engine",
  "target": "BTC/USDT",
  "channels": ["7168024869", "1191689637"]
}
```

**`GET /api/scan?asset=BTC/USDT&send_telegram=true`** — Manual scan trigger
- `asset`: any crypto pair (default: `BTC/USDT`)
- `send_telegram`: whether to broadcast signal to Telegram (default: `true`)
- Handles crypto (USDT pairs) vs stocks (no slash) automatically
- Includes live price fetch
- Deduplication: checks if same OB already sent → skips if yes
- Returns full analysis dict + formatted message

**`POST /api/webhook/tradingview`** — TradingView alert receiver
- **Scenario 1** — Pre-formatted message:
  ```json
  {"message": "🟢 BUY SIGNAL — BTC/USDT\nEntry: 63450\nSL: 63377"}
  ```
  → Sends message directly to Telegram as-is.

- **Scenario 2** — Dynamic trigger:
  ```json
  {"asset": "BTC/USDT", "action": "BUY"}
  ```
  → Runs full SMC scan and sends signal if valid.

#### UTF-8 Fix (Windows)
```python
# Top of app.py — prevents emoji crash on Windows cp1252 console
import sys, io
if sys.stdout.encoding != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
```

#### Duplicate Signal Guard
```python
raw_ob = analysis.get("raw_ob", {})
ob_key = (raw_ob.get("candle_index"), raw_ob.get("type"))  # Unique ID for each OB

if last_sent_signals[asset]["ob_key"] == ob_key:
    print("Already sent this OB. Skipping.")
else:
    telegram_bot.send_message(formatted_msg)
    last_sent_signals[asset] = {"ob_key": ob_key, "timestamp": time.time()}
```

---

### 4.2 `config.py` — Settings

**Path:** `d:\Trading bots\Demand Supply Trading bot\config.py`  
**Size:** 27 lines  
**Role:** Single source of truth for all configuration. Uses pydantic-settings for automatic `.env` loading.

```python
class Settings(BaseSettings):
    # Telegram
    TELEGRAM_BOT_TOKEN: str = ""            # Required — get from @BotFather
    TELEGRAM_CHAT_IDS: str = "7168...,1191..."  # Comma-separated chat IDs

    # LLM
    GEMINI_API_KEY: str = ""                # Optional — enables AI signal formatting
    OPENAI_API_KEY: str = ""                # Optional — not currently used
    USE_LLM_FORMATTER: bool = True          # Set False to always use template

    # Strategy
    DEFAULT_ASSETS: list[str] = ["BTC/USDT", "ETH/USDT", "SOL/USDT"]
    SL_BUFFER_PIPS: float = 3.0             # Points beyond OB for SL

    # Server
    PORT: int = 8000
    HOST: str = "0.0.0.0"

    class Config:
        env_file = ".env"
        extra = "ignore"                    # Ignores unknown .env vars
```

#### To Add a New Asset
Just add to `DEFAULT_ASSETS`:
```python
DEFAULT_ASSETS: list[str] = ["BTC/USDT", "ETH/USDT", "SOL/USDT", "DOGE/USDT"]
```
No other code changes needed — the scheduler and fetcher handle it automatically.

---

### 4.3 `core/smc_engine.py` — Strategy Brain

**Path:** `d:\Trading bots\Demand Supply Trading bot\core\smc_engine.py`  
**Size:** ~400 lines  
**Role:** All SMC calculation logic. This is the core intelligence of the bot.

#### Method: `calculate_atr(df, period=14)` → `float`
```
Calculates Average True Range using Exponential Weighted Moving Average.

True Range = max(
  High − Low,
  |High − Previous Close|,
  |Low − Previous Close|
)

ATR = EWM(True Range, span=14)
Fallback = mean(High − Low) if result is NaN

Returns: float (current ATR value)
```
Used as: the volatility baseline for all dynamic thresholds in the strategy.

---

#### Method: `detect_15m_trend(df_15m, window=5)` → `str`

**Returns:** `"BULLISH"` | `"BEARISH"` | `"SIDEWAYS"`

**Primary Method — Market Structure:**
```
For each candle i in the 15M series:
  Swing High: highs[i] == max(highs[i-5 : i+6])  → 11-candle window
  Swing Low:  lows[i]  == min(lows[i-5  : i+6])

Take last 2 swing highs (SH1=latest, SH2=previous)
Take last 2 swing lows  (SL1=latest, SL2=previous)

BULLISH: SH1 > SH2 AND SL1 > SL2   (Higher Highs + Higher Lows)
BEARISH: SH1 < SH2 AND SL1 < SL2   (Lower Highs  + Lower Lows)
Mixed  : → fall through to EMA fallback
```

**When EMA Fallback is Used:**
- Insufficient swing structure detected
- Swing range < 2 × ATR (market too flat to confirm structure)

**Fallback — EMA Crossover:**
```
EMA20 > EMA50 AND Close > EMA20  → BULLISH
EMA20 < EMA50 AND Close < EMA20  → BEARISH
Otherwise                         → SIDEWAYS
```

---

#### Method: `find_3m_order_blocks(df_3m, trend, atr, lookback=30)` → `List[Dict]`

Scans the **last 30 candles** of the 3M chart for Order Block patterns.

**Impulse Threshold:**
```
impulse_threshold = 1.5 × ATR(14)
Only consider candle[i+1] as "strong move" if |close[i+1] - close[i]| > threshold
```

**Bullish OB Detection:**
```
candle[i]:   Close < Open     (red/bearish candle)
candle[i+1]: Close > close[i] AND move > 1.5×ATR  (strong bullish expansion)

OB Zone:
  high   = candle[i].High
  low    = candle[i].Low
  top    = max(candle[i].Open, candle[i].Close)
  bottom = candle[i].Low
  mid    = (high + low) / 2
```

**Bearish OB Detection:**
```
candle[i]:   Close > Open     (green/bullish candle)
candle[i+1]: Close < close[i] AND move > 1.5×ATR  (strong bearish expansion)

OB Zone:
  high   = candle[i].High
  low    = candle[i].Low
  top    = candle[i].High
  bottom = min(candle[i].Open, candle[i].Close)
  mid    = (high + low) / 2
```

**OB Dict Structure:**
```python
{
  "type": "BULLISH" | "BEARISH",
  "high": float,        # OB candle's wick high
  "low": float,         # OB candle's wick low
  "top": float,         # OB body top
  "bottom": float,      # OB body bottom
  "mid": float,         # midpoint (high + low) / 2
  "midpoint": float,    # same as mid (compatibility alias)
  "candle_index": int,  # index in the 30-candle subset
  "index": int          # same as candle_index
}
```

---

#### Method: `is_ob_still_valid(subset_df, ob)` → `bool`

Checks if an OB has been **mitigated** (price already traded through it).

```
For each candle AFTER the OB formed:

  Bullish OB invalid if:  any candle's CLOSE < OB low
  (price closed below the OB — institutions already absorbed, zone used up)

  Bearish OB invalid if:  any candle's CLOSE > OB high
  (price closed above the OB — zone used up)

Returns True  = OB is still fresh, not mitigated → valid to trade
Returns False = OB already mitigated → skip, don't trade
```

---

#### Method: `detect_3m_fvg(df_3m, trend, lookback=20)` → `List[Dict]`

Finds **Fair Value Gaps** (3-candle imbalance patterns) in the last 20 candles.

**Bullish FVG:**
```
candle[i+2].Low > candle[i].High
              ↑ gap ↑
FVG Zone:
  top    = candle[i+2].Low   (bottom of the 3rd candle)
  bottom = candle[i].High    (top of the 1st candle)
  gap = top - bottom         (size of the imbalance)
```

**Bearish FVG:**
```
candle[i+2].High < candle[i].Low
              ↑ gap ↑
FVG Zone:
  top    = candle[i].Low
  bottom = candle[i+2].High
```

**FVG Dict Structure:**
```python
{
  "type": "BULLISH" | "BEARISH",
  "high": float,
  "low": float,
  "top": float,
  "bottom": float,
  "mid": float,
  "gap_size": float,
  "candle_index": int,
  "index": int
}
```

---

#### Method: `check_confirmation(df_3m, trend, active_ob)` → `(bool, str)`

Returns `(confirmed: bool, confirmation_type: str)`.

Checks the **last two candles** of the 3M chart for a reversal signal at the OB zone:

**Type 1 — Engulfing Candle** (strongest signal):
```
BULLISH engulfing (for BUY):
  Current: Close > Open (green)
  Current Close > Previous Open  (current body engulfs previous)
  Current Open  < Previous Close

BEARISH engulfing (for SELL):
  Current: Close < Open (red)
  Current Close < Previous Open
  Current Open  > Previous Close
```

**Type 2 — Strong Wick Rejection** (strong signal):
```
BULLISH wick rejection (for BUY):
  Current candle LOW taps inside OB zone:
    ob_low <= candle.Low <= ob_high
  Lower wick length > 1.5 × candle body size

BEARISH wick rejection (for SELL):
  Current candle HIGH taps inside OB zone:
    ob_low <= candle.High <= ob_high
  Upper wick length > 1.5 × candle body size
```

**Type 3 — OB Midpoint Close** (moderate signal):
```
BULLISH: Current candle Close > OB midpoint
BEARISH: Current candle Close < OB midpoint
```

---

#### Method: `analyze_setup(asset_name, df_15m, df_3m, sl_buffer=3.0, live_price=None)` → `Dict`

The **full pipeline**. Runs all 10 steps in sequence:

```
Step 1: Volume guard
  → if df_3m["volume"].iloc[-1] == 0:
       return {"valid": False, "reason": "CANDLE_NOT_CLOSED_YET"}

Step 2: 15M Trend
  → if SIDEWAYS: return no-trade

Step 3: Find 3M OBs matching trend direction
  → if no OBs found: return no-trade

Step 4: Take most recent OB (matching_obs[-1])
  → Check is_ob_still_valid() → if mitigated: return no-trade

Step 5: FVG Confluence Check (atr_limit = 1.0 × ATR)
  → Overlap: min(ob_high, fvg_high) - max(ob_low, fvg_low) > 0
  → OR distance: |ob_mid - fvg_mid| <= atr_limit
  → if no confluence: return no-trade

Step 6: Confirmation Check
  → check_confirmation() → if not confirmed: return no-trade

Step 7: Entry Price
  → curr_price = live_price (if available) else df_3m["close"].iloc[-1]

Step 8: SL & TP Calculation
  BUY:  sl = ob_low - sl_buffer
        risk = curr_price - sl
        tp1  = curr_price + risk       (1:1 RR)
        tp2  = curr_price + risk × 2   (1:2 RR)

  SELL: sl = ob_high + sl_buffer
        risk = sl - curr_price
        tp1  = curr_price - risk
        tp2  = curr_price - risk × 2

Step 9: Return valid signal dict
```

**Return dict (valid signal):**
```python
{
  "valid": True,
  "signal_type": "BUY" | "SELL",
  "asset": str,
  "trend_15m": "BULLISH" | "BEARISH",
  "setup": "Order Block + FVG on 3M",
  "confirmation": str,            # e.g. "Bullish Engulfing at OB Zone"
  "entry": float,
  "stop_loss": float,
  "tp1": float,
  "tp2": float,
  "estimated_hold": "15–40 min",
  "confidence": "HIGH" | "MODERATE",
  "raw_ob": dict,                 # full OB dict (used for duplicate guard)
  "has_fvg": bool
}
```

---

### 4.4 `core/data_fetcher.py` — Market Data

**Path:** `d:\Trading bots\Demand Supply Trading bot\core\data_fetcher.py`  
**Size:** ~191 lines  
**Role:** Fetches OHLCV candle data and live prices. Handles all data source fallbacks.

#### Data Source Hierarchy (Crypto)
```
Priority 1: yfinance Ticker.history()   ← Always tried first
  ↓ (if fails)
Priority 2: CCXT Bybit spot             ← Network fallback
  ↓ (if fails)
Priority 3: Simulated candles           ← Last resort (realistic prices, random walk)
```

**Why yfinance is Primary:**  
Binance API (`api.binance.com`) and Bybit API (`api.bybit.com`) are **ISP-blocked in India since 2024**. All calls return connection refused. Yahoo Finance has global CDN with no geo-restrictions.

#### Method: `_symbol_to_yf(symbol)` → `str`
```
BTC/USDT  → BTC-USD
ETH/USDT  → ETH-USD
BTCUSDT   → BTC-USD
SOL/USDT  → SOL-USD

Logic:
  if "/" in symbol: base = symbol.split("/")[0]
  elif ends with "USDT": base = symbol[:-4]
  yf_symbol = f"{base}-USD"
```

#### Method: `fetch_crypto_candles(symbol, timeframe, limit=100)` → `DataFrame`

**yfinance interval mapping:**
```
"3m"  → "2m"   (Yahoo's minimum is 2m; close enough for SMC analysis)
"15m" → "15m"  (exact match)
"5m"  → "5m"
"1m"  → "1m"
"1h"  → "60m"
```

**Why `Ticker().history()` not `download()`:**  
`yf.download()` has a known multi-ticker caching bug — when downloading BTC-USD then ETH-USD in rapid succession, ETH sometimes gets BTC's cached data back. `Ticker("ETH-USD").history()` is fully isolated per-ticker with no cross-contamination.

**DataFrame columns returned:**
```
timestamp | open | high | low | close | volume
```
All float64, timestamp as datetime64.

**RAW CHECK log line:**
```
[RAW CHECK] ETH-USD 15m last close = 1883.6300 (via yfinance Ticker)
```
This line appears in server logs every fetch — use it to instantly verify prices are real.

#### Method: `fetch_live_price(symbol)` → `Optional[float]`

```python
# Primary: yfinance fast_info
ticker = yf.Ticker("BTC-USD")
info = ticker.fast_info
price = info.last_price or info.regularMarketPrice

# Fallback: CCXT Bybit fetch_ticker
ticker_data = self.exchange.fetch_ticker("BTC/USDT")
price = ticker_data["last"]
```

#### Simulated Candle Prices (Fallback — Last Resort)
```
BTC  : $59,000  base  (Aug 2024 approx)
ETH  : $1,560
SOL  : $73
NIFTY: $24,500

Random walk: prices change by 0.1% per candle (realistic noise)
Volume:  100–1000 (random, distinct from other assets)
```

---

### 4.5 `core/scheduler.py` — Background Scheduler

**Path:** `d:\Trading bots\Demand Supply Trading bot\core\scheduler.py`  
**Size:** 69 lines  
**Role:** Runs the automatic scan loop, synchronized precisely to 3M candle close boundaries.

#### How It Aligns to Candle Closes
```python
def wait_for_candle_close(timeframe_minutes=3):
    now = time.time()
    seconds_in_tf = 3 * 60         # 180 seconds
    sleep_time = 180 - (now % 180) # seconds until next 3M boundary
    time.sleep(sleep_time)
```

**Example:**  
If it's currently 02:47:23 (hh:mm:ss), the next 3M boundary is 02:48:00.  
`sleep_time = 180 - (47*60+23) % 180 = 180 - 37 = 37 seconds`  
Bot sleeps 37 seconds, wakes at exactly 02:48:00, then scans.

#### Main Loop
```python
while self.running:
    wait_for_candle_close(timeframe_minutes=3)  # Sleep until boundary
    job()                                        # Scan all assets
    time.sleep(10)                               # Step 10s past boundary (avoids re-trigger)
```

The 10-second buffer after scanning prevents the next `time.time() % 180` from being 0 (edge case where we'd immediately sleep 0 seconds and scan again).

#### Job Function
```python
def job():
    from app import scan_asset        # Imported here to avoid circular import
    for asset in settings.DEFAULT_ASSETS:   # ["BTC/USDT", "ETH/USDT", "SOL/USDT"]
        try:
            scan_asset(asset=asset, send_telegram=True)
        except Exception as e:
            print(f"Error scanning {asset}: {e}")
```

---

### 4.6 `core/llm_signal.py` — Signal Formatter

**Path:** `d:\Trading bots\Demand Supply Trading bot\core\llm_signal.py`  
**Size:** 251 lines  
**Role:** Converts raw analysis dict into human-readable Telegram signal message. Two modes: Gemini AI or template.

#### `SignalFormatter.SYSTEM_PROMPT`
A detailed system prompt telling Gemini exactly what format to use. Includes:
- The exact BUY template with box-drawing characters
- The exact SELL template
- The NO SETUP template
- Rules: never change prices, no analysis, plain text only

#### Method: `format_signal(data)` → `str`

**Step 1 — Get IST timestamp:**
```python
tz_ist = pytz.timezone('Asia/Kolkata')
now_ist = datetime.now(tz_ist)
timestamp_str = now_ist.strftime("%H:%M IST | %d-%m-%Y")
# e.g. "02:45 IST | 03-08-2026"
```

**Step 2 — If no valid signal:**
```
→ Try Gemini first (if API key + quota available)
→ Fallback: "⏳ SCAN COMPLETE — {asset}\n⏰ {timestamp}\n\nNo valid setup detected.\nReason: {reason}"
```

**Step 3 — Validation checks (before formatting valid signal):**
```python
# TREND_DIRECTION_CONFLICT
if direction == "BUY" and trend_15m != "BULLISH":
    return "NULL_SIGNAL with reason: TREND_DIRECTION_CONFLICT"

# INVALID_SL_PLACEMENT
if direction == "BUY" and sl >= entry:
    return "NULL_SIGNAL with reason: INVALID_SL_PLACEMENT"

# TP_LEVEL_MISCALCULATED
target_tp1 = entry + risk if BUY else entry - risk
if abs(tp1 - target_tp1) / entry > 0.001:   # > 0.1% deviation
    return "NULL_SIGNAL with reason: TP_LEVEL_MISCALCULATED"
```

**Step 4 — Format with Gemini (if quota available):**
```python
client = genai.Client(api_key=settings.GEMINI_API_KEY)
response = client.models.generate_content(
    model="gemini-2.0-flash",
    contents=f"{SYSTEM_PROMPT}\n\nFormat this signal: {json.dumps(payload)}"
)
return response.text.strip()
```

**Step 5 — Template fallback (always available):**
```
╔═══════════════════════╗
║  🟢 BUY  •  BTC/USDT ║
╚═══════════════════════╝
⏰ 02:45 IST | 03-08-2026

✅ 15M Trend  : Bullish
🧱 Zone       : Order Block + Fair Value Gap
⚡ Trigger    : Bullish Engulfing at OB Zone

┌──────────────────────┐
│ 🎯 Entry  →  63450   │
│ 🛑 SL     →  63377   │
│ 💰 TP1    →  63523   │
│ 💰 TP2    →  63596   │
└──────────────────────┘
⏱ Hold  : 15–40 min
📊 Confidence : 🔥 HIGH
─────────────────────────
⚠️ Not financial advice. DYOR.
```

**Confirmation label mapping:**
```
"Engulfing"   → "Bullish/Bearish Engulfing Candle"
"Rejection"   → "Strong Wick Rejection at OB"
(else)        → "Close Beyond OB Midpoint"
```

**Confidence display:**
```
"HIGH"     → "🔥 HIGH"
"MODERATE" → "⚡ MODERATE"
```

---

### 4.7 `bot/telegram_bot.py` — Signal Sender

**Path:** `d:\Trading bots\Demand Supply Trading bot\bot\telegram_bot.py`  
**Size:** 52 lines  
**Role:** Sends formatted signal text to all configured Telegram chats via direct HTTP POST.

**Does NOT use `parse_mode`** — signal messages use box-drawing characters and emojis that trip Telegram's strict Markdown parser. Plain text mode renders them perfectly.

```python
payload = {
    "chat_id": cid,
    "text": text
    # NO parse_mode — avoids "Can't parse entities" 400 error
}
resp = requests.post(
    f"https://api.telegram.org/bot{token}/sendMessage",
    json=payload,
    timeout=10
)
```

**Multi-chat support:**
```python
# config.py → TELEGRAM_CHAT_IDS = "7168024869,1191689637"
# Splits by comma → sends to each chat ID independently
for cid in self.chat_ids:
    requests.post(url, json={..., "chat_id": cid})
```

---

### 4.8 `bot/telegram_listener.py` — Command Handler

**Path:** `d:\Trading bots\Demand Supply Trading bot\bot\telegram_listener.py`  
**Size:** 373 lines  
**Role:** Runs a polling loop in a background thread, handling user commands via Telegram.

#### `normalize_asset(raw)` → `str`
```python
# Handles all input formats:
"BTCUSDT"   → "BTC/USDT"    (ends with USDT → insert /)
"btcusdt"   → "BTC/USDT"    (uppercased first)
"ETH/USDT"  → "ETH/USDT"    (already correct)
"ETHBUSD"   → "ETH/BUSD"    (BUSD support)
"SOLXYZ"    → "SOL/XYZ"     (6+ chars → splits last 3)
```

#### `execute_scan(update, asset)`
1. Sends "Fetching candles..." acknowledgment
2. Fetches 15M + 3M candles via `MarketDataFetcher`
3. Fetches live price
4. Runs `SMCEngine.analyze_setup()`
5. Formats with `SignalFormatter.format_signal()`
6. Sends result back to the user (no `parse_mode`)
7. On exception: sends actual error text (not generic "check ticker name")

#### `execute_debug(update, asset)`
Full diagnostic truth test. Shows:
- Raw candle data (OHLCV for last 15M and 3M bars)
- ATR calculation
- Swing high/low values + swing range
- Min swing range threshold
- OB found? If yes: OB high/low/type
- FVG found? OB↔FVG distance vs ATR threshold
- Confluence valid?
- Confirmation check result
- Final signal output
- VERDICT: REAL DATA ✅ or DATA BUG DETECTED ❌

#### Sanity Checks in `/debug`:
```python
checks = {
    "TF_PRICE_MATCH":     abs(15M_close - 3M_close) < 30 × ATR,
    "VOLUME_DIFFERENT":   vol_15m != vol_3m,
    "SWING_RANGE_VALID":  swing_range > 2 × ATR_15m,
    "ATR_REALISTIC":      10 < ATR < 1000,
    "OB_NOT_SWING_COPY":  ob_high != swing_high AND ob_low != swing_low
}
```

#### `handle_all_messages(update, context)`
Catches ALL text messages (not just slash commands) and routes them:
- Strips leading emojis/symbols first (keyboard buttons send "🔍 SCAN BTC/USDT")
- Then matches against "SCAN", "/SCAN", "DEBUG", "/DEBUG", "WATCHLIST", "/START"
- This is what makes keyboard buttons work seamlessly

#### `run_telegram_listener()`
```python
while True:                              # Outer retry loop
    try:
        application = Application.builder()...build()
        application.add_handler(CommandHandler("scan", scan))
        application.add_handler(CommandHandler("debug", debug))
        application.add_handler(CommandHandler("watchlist", watchlist))
        application.add_handler(MessageHandler(filters.TEXT, handle_all_messages))
        application.run_polling()        # Blocking — polls Telegram every 10s
    except Exception as e:
        print(f"Connection error. Retrying in 10 seconds...")
        time.sleep(10)                   # Auto-reconnects on any network failure
```

#### `/start` Welcome Message
```
🤖 SMC Pullback Strategy Engine v2.1 🤖

Welcome! I am your automated SMC trading assistant...

[🔍 SCAN BTC/USDT] [🧪 DEBUG BTC/USDT]
[🔍 SCAN ETH/USDT] [📈 WATCHLIST    ]
```

---

### 4.9 `tests/test_smc_engine.py` — Unit Tests

**Path:** `d:\Trading bots\Demand Supply Trading bot\tests\test_smc_engine.py`  
**Size:** 84 lines  
**Status:** 3 tests, all passing ✅

#### `setUp()` — Synthetic Data Generation
Creates realistic test candles:
- **15M data:** 50 candles, linearly trending from 100 → 200 (clearly bullish)
- **3M data:** 30 candles with manually injected OB at index 10, confirmation at index 29

**Injected OB at index 10:**
```python
df_3m.loc[10] = [152, 153, 148, 149]  # Red OB candle
df_3m.loc[11] = [149, 157, 149, 156]  # Strong green impulse (7-point move)
df_3m.loc[12] = [156, 162, 156, 161]  # Expansion
```

**Injected confirmation at index 29:**
```python
df_3m.loc[28] = [151, 152, 148.5, 149.5]  # Red pullback (reversal candle)
df_3m.loc[29] = [149.5, 155, 149, 154]    # Green engulfing (confirmation)
```

#### `test_trend_detection()`
Asserts `detect_15m_trend()` returns one of the three valid values.

#### `test_smc_analysis()`
If a valid signal is found, asserts:
- `signal_type == "BUY"` (data is bullish)
- `tp1 > entry`
- `tp2 > tp1`
- `stop_loss < entry`

#### `test_telegram_signal_format()`
Tests `SignalFormatter.format_signal()` with hardcoded sample data.
Asserts the output string contains:
- `"🟢 BUY  •  BTC/USDT"`
- `"✅ 15M Trend  : Bullish"`
- `"🎯 Entry  →  65000.0"`
- etc.

**Run tests:**
```bash
python -m unittest tests/test_smc_engine.py -v
```

---

### 4.10 `.env` / `.env.example` — Environment Config

**`.env.example`** (safe to commit):
```env
TELEGRAM_BOT_TOKEN=your_telegram_bot_token_here
TELEGRAM_CHAT_ID=your_telegram_channel_or_chat_id_here
GEMINI_API_KEY=your_gemini_api_key_here
OPENAI_API_KEY=your_openai_api_key_here
USE_LLM_FORMATTER=True
HOST=0.0.0.0
PORT=8000
```

**`.env`** (never commit — contains real secrets):
- Loaded automatically by pydantic-settings via `env_file = ".env"`
- Values override `config.py` defaults

---

## 5. Signal Logic — How Entries, SL & TP Are Calculated

### Entry Price
```
Primary:  Live price from yfinance fast_info (real-time tick)
Fallback: df_3m["close"].iloc[-1] (last closed 3M candle close)

→ Entry = current market price at moment of signal generation
→ NOT a limit order — entry is at market when signal fires
```

### Stop Loss
```
BUY signal:   SL = OB_Low  − SL_Buffer (default 3.0 points)
SELL signal:  SL = OB_High + SL_Buffer

Rationale: If price closes beyond the OB, the setup is invalidated.
The 3-point buffer prevents SL being hit by minimal wick extensions.
```

### Take Profit
```
Risk = |Entry − Stop Loss|

TP1 (1:1 Risk-Reward):
  BUY:   TP1 = Entry + Risk
  SELL:  TP1 = Entry − Risk

TP2 (1:2 Risk-Reward):
  BUY:   TP2 = Entry + (Risk × 2)
  SELL:  TP2 = Entry − (Risk × 2)
```

### Example — BUY Signal
```
OB detected:   Low = 63,380   High = 63,420
Entry (live):  63,450
SL:            63,380 − 3 = 63,377
Risk:          63,450 − 63,377 = 73 points

TP1:           63,450 + 73  = 63,523  (1:1)
TP2:           63,450 + 146 = 63,596  (1:2)
Hold:          15–40 minutes
```

---

## 6. Timeframe Logic — How 15M + 3M Work Together

```
15M CHART (100 candles = ~25 hours of data)
───────────────────────────────────────────
Purpose: Determine the MACRO BIAS
  - Are institutions buying or selling overall?
  - Are we in a higher timeframe uptrend or downtrend?
  - SIDEWAYS = don't trade (no clear direction)

Signal from 15M: "The overall bias is BULLISH"

         ↓ ONLY if BULLISH or BEARISH (not SIDEWAYS)

3M CHART (100 candles = ~5 hours of data)
──────────────────────────────────────────
Purpose: Find the PRECISE ENTRY ZONE
  - Where did institutions last place their buy orders? (Order Block)
  - Is there a price imbalance nearby? (Fair Value Gap)
  - Is price pulling back INTO that zone right now?
  - Has price shown a reversal signal there? (Confirmation)

Signal from 3M: "Price is at the OB+FVG zone with a bullish engulfing"

         ↓ ONLY if ALL 3M conditions met

SIGNAL FIRES:
  Entry: current market price
  SL:    below OB low
  TP1:   1:1 risk-reward
  TP2:   1:2 risk-reward
```

**The key principle:** The 15M timeframe tells you WHERE the market wants to go. The 3M timeframe tells you WHERE to get in at the best price, closest to where you'd be wrong (the OB). This minimizes risk while maximizing reward.

---

## 7. Data Flow — End to End

```
[3M CANDLE CLOSES] → scheduler wakes up
       │
       ▼
[MarketDataFetcher.fetch_crypto_candles("BTC/USDT", "15m", 100)]
  → yf.Ticker("BTC-USD").history(period="2d", interval="15m")
  → Returns 100 rows: [timestamp, open, high, low, close, volume]
       │
[MarketDataFetcher.fetch_crypto_candles("BTC/USDT", "3m", 100)]
  → yf.Ticker("BTC-USD").history(period="2d", interval="2m")
  → Returns 100 rows
       │
[MarketDataFetcher.fetch_live_price("BTC/USDT")]
  → yf.Ticker("BTC-USD").fast_info.last_price
  → Returns: 63450.18
       │
       ▼
[SMCEngine.analyze_setup("BTC/USDT", df_15m, df_3m, live_price=63450.18)]
  │
  ├─ volume guard (vol=0 → skip)
  ├─ detect_15m_trend(df_15m) → "BULLISH"
  ├─ find_3m_order_blocks(df_3m, "BULLISH", atr) → [ob1, ob2]
  ├─ is_ob_still_valid(df_3m, ob2) → True
  ├─ detect_3m_fvg(df_3m, "BULLISH") → [fvg1]
  ├─ confluence check: |ob_mid - fvg_mid| = 18.5 < 1×ATR(23) ✅
  ├─ check_confirmation(df_3m, "BULLISH", ob2) → (True, "Bullish Engulfing at OB Zone")
  └─ Returns valid signal dict: {entry:63450, sl:63377, tp1:63523, tp2:63596}
       │
       ▼
[SignalFormatter.format_signal(analysis)]
  │
  ├─ Gemini 2.0 Flash (if quota available)
  └─ Template fallback → formats box-drawing signal text
       │
       ▼
[Duplicate guard: ob_key (candle_index=24, type="BULLISH") already sent?]
  → No → proceed
  → Yes → skip
       │
       ▼
[TelegramSignalBot.send_message(formatted_text)]
  → POST https://api.telegram.org/bot.../sendMessage
  → {chat_id: "7168024869", text: "╔═══..."}
  → {chat_id: "1191689637", text: "╔═══..."}
       │
       ▼
[TELEGRAM CHANNEL receives signal] 🎉
```

---

## 8. Telegram Commands Reference

| Command | Example | Result |
|---|---|---|
| `/start` | `/start` | Welcome message + keyboard buttons |
| `/scan` | `/scan` | Scans BTC/USDT |
| `/scan <asset>` | `/scan ETH/USDT` | Scans ETH/USDT |
| `/scan <asset>` | `/scan SOLUSDT` | Auto-normalizes → SOL/USDT |
| `/debug` | `/debug` | BTC/USDT full diagnostic |
| `/debug <asset>` | `/debug ETH/USDT` | Full truth test for ETH |
| `/watchlist` | `/watchlist` | Shows: BTC/USDT · ETH/USDT · SOL/USDT |
| Button: `🔍 SCAN BTC/USDT` | (tap) | Same as `/scan BTC/USDT` |
| Button: `🔍 SCAN ETH/USDT` | (tap) | Same as `/scan ETH/USDT` |
| Button: `🧪 DEBUG BTC/USDT` | (tap) | Same as `/debug BTC/USDT` |
| Button: `📈 WATCHLIST` | (tap) | Same as `/watchlist` |

**Asset formats accepted:**
```
BTC/USDT  ✅  (standard)
BTCUSDT   ✅  (auto-normalized)
btcusdt   ✅  (lowercase, auto-normalized)
BTC USDT  ✅  (space, handled)
ETH       ⚠️  (ambiguous, defaults to ETH/USD)
```

---

## 9. Complete Bug Fix Changelog

### Round 1 — Data Integrity
| # | Bug | Symptom | Root Cause | Fix |
|---|---|---|---|---|
| 1 | Price sanity check false positive | `TF_PRICE_MATCH` always failing | `MAX_TF_PRICE_DIFF = 100` (hardcoded) too tight — BTC can move $482 between 15M close and 3M open normally | Changed to `30 × ATR` (dynamic per volatility) |
| 2 | FVG confluence too tight | No signals even with valid OB+FVG | `FVG_OB_ATR_MULT = 0.5` — OB and FVG had to be within half an ATR | Changed to `1.0 × ATR` |
| 3 | Swing range false fail | `SWING_RANGE_VALID` blocking signals in low vol | `MIN_SWING_RANGE = 100` hardcoded — BTC sometimes ranges only $73 | Changed to `2 × ATR` |
| 4 | Stale OB from 50 candles ago | Signal fires on dead zone already mitigated | OB detection iterated ALL candles | Limited to `RECENT_CANDLES = 30` |
| 5 | Mitigated OB still trading | Signal fires after price already broke through OB | `is_ob_still_valid()` written but not called | Wired into `analyze_setup()` |

### Round 2 — Asset Issues
| # | Bug | Symptom | Root Cause | Fix |
|---|---|---|---|---|
| 6 | SOL showing $858 (10× real) | SOL real = $73, bot showed $730–858 | CCXT `defaultType: 'future'` — Binance futures SOL contract = 10 SOL | Changed to `defaultType: 'spot'` |
| 7 | All crypto blocked | `binance GET /api/v3/exchangeInfo` error | Binance + Bybit APIs ISP-blocked in India | Switched to yfinance as primary |
| 8 | ETH 15M returning BTC price | ETH signal using BTC price → math crash → error | `yf.download()` cross-ticker cache bug | Switched to `yf.Ticker().history()` |
| 9 | Bot only scans BTC | `/scan ETH/USDT` silently scans BTC instead | `scan_asset()` hardcoded `"BTC/USDT"` | Made asset dynamic from parameter |

### Round 3 — Signal Quality
| # | Bug | Symptom | Root Cause | Fix |
|---|---|---|---|---|
| 10 | Mid-candle signals | Entry price unreliable (shifts before candle closes) | Bot scanned live (open) candles | Added `volume == 0` guard at top of `analyze_setup()` |
| 11 | Duplicate signals | Same OB fires signal every 3M scan | No deduplication | Added `last_sent_signals` dict keyed by `(candle_index, type)` per asset |
| 12 | Simulated prices when live fails | Wrong prices silently used | Hardcoded fallback: SOL=$150, ETH=$3,400 | Updated to Aug 2024 real values: $73, $1,560, $59,000 |

### Round 4 — Telegram / Delivery
| # | Bug | Symptom | Root Cause | Fix |
|---|---|---|---|---|
| 13 | "⚠️ Error executing scan for BTC/USDT" | Scan succeeds internally but user gets error | `reply_text(..., parse_mode="Markdown")` returns `400 Bad Request` from Telegram — box-drawing chars trip Markdown parser | Removed `parse_mode` from `reply_text()` and `send_message()` |
| 14 | Generic error message hides real issue | "Please check ticker name" even for non-ticker errors | `except Exception: reply("⚠️ Error executing scan...")` | Changed to `reply(f"Error: {e}")` — shows actual exception |
| 15 | Emoji crash in server logs | `UnicodeEncodeError: 'charmap' codec` | Windows `cp1252` console encoding doesn't support emoji | Added UTF-8 `TextIOWrapper` wrap at `app.py` startup |
| 16 | `/scanBTC/USDT` (no space) failing | Bot doesn't respond | Command parser split on space → `/scanBTC/USDT` is one token | Added `handle_all_messages()` with prefix matching |
| 17 | Keyboard buttons not working | "🔍 SCAN BTC/USDT" text not recognized | Message handler not registered | Added `MessageHandler(filters.TEXT, handle_all_messages)` |

### Round 5 — Architecture
| # | Feature Added | Details |
|---|---|---|
| 18 | Multi-asset auto-scanning | Scheduler scans BTC + ETH + SOL every 3M close automatically |
| 19 | Live price for entry | `fetch_live_price()` → entry uses real-time tick, not candle close |
| 20 | `/debug` diagnostic command | Full raw SMC truth test showing every intermediate calculation |
| 21 | Keyboard button UI | `/start` shows 4 quick-action buttons |
| 22 | Auto-reconnect listener | `run_telegram_listener()` retries every 10s on network failure |
| 23 | TradingView webhook | `/api/webhook/tradingview` accepts external alerts |
| 24 | Project documentation | `docs/signal_logic.md` + `docs/project_documentation.md` |

---

## 10. Known Limitations & Future Work

### Current Limitations

| Limitation | Impact | Potential Fix |
|---|---|---|
| Gemini API free tier quota (429) | Signal formatting falls back to template | Upgrade to paid tier OR implement rate limiter with backoff |
| yfinance "2m" interval instead of "3m" | Slight timing mismatch (Yahoo's minimum is 2m) | Acceptable for SMC — OB/FVG zones don't change at 2m precision |
| No backtesting module | Can't verify historical accuracy | Add backtesting engine using historical yfinance data |
| Confirmation wait causes delay | Signal may fire 1 candle after ideal entry | Acceptable — reduces false signals significantly |
| No position tracking | Bot doesn't know if you're already in a trade | Add state machine with open/close position tracking |
| SL_BUFFER hardcoded to 3 pips | May be too tight for high-volatility assets | Make it ATR-based: `0.1 × ATR` |
| Single live listener thread | One crash brings down all commands | Separate threads per handler OR use webhooks instead of polling |

### Recommended Next Steps
1. **Paid Gemini API** → AI-formatted signals always (template is functional but plain)
2. **Backtesting** → Run strategy on 6 months of history, measure win rate
3. **Win rate tracking** → Log each signal + outcome in a SQLite DB
4. **ATR-based SL buffer** → `SL = OB_low - (0.1 × ATR)` instead of fixed 3 pips
5. **More assets** → Add DOGE, MATIC, ADA to watchlist in `config.py`
6. **TradingView integration** → Set up TV alerts to hit the webhook endpoint
