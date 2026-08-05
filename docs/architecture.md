# SMC Pullback Strategy Bot — System Architecture v2.1

A complete architectural blueprint detailing data flow, concurrency, proxying, fallback mechanisms, and signal delivery pipelines.

---

## 🏗️ System Architecture Overview

```
                               ┌─────────────────────────────┐
                               │     TradingView Webhooks    │
                               └──────────────┬──────────────┘
                                              │ POST /api/webhook/tradingview
                                              ▼
 ┌──────────────────────┐      ┌─────────────────────────────┐      ┌──────────────────────┐
 │    Binance/Bybit     ├─────►│        FastAPI Server       │◄─────┤    Yahoo Finance     │
 │   (CCXT Fallback)    │      │        (Port 8000)          │      │  (yfinance + Cache)  │
 └──────────────────────┘      └──────────────┬──────────────┘      └──────────────────────┘
                                              │ Starts Async Lifespan & Threads
                                              ├───────────────────────────────┐
                                              ▼                               ▼
                               ┌─────────────────────────────┐  ┌─────────────────────────────┐
                               │   TradingBotScheduler (3M)  │  │   Telegram Command Listener │
                               │   Aligns loop to 3M boundary│  │   (Polling / Webhook mode)  │
                               └──────────────┬──────────────┘  └──────────────┬──────────────┘
                                              │                               │
                                              ├───────────────────────────────┘
                                              │ Trigger SMC Scan Analysis
                                              ▼
                               ┌─────────────────────────────┐
                               │         SMC Engine          │
                               │  1. Volume == 0 Guard       │
                               │  2. 15M Structural Trend    │
                               │  3. 3M Order Block (OB)     │
                               │  4. 3M Fair Value Gap (FVG) │
                               │  5. 2-Candle Confirmation   │
                               │  6. Dynamic SL/TP Math      │
                               └──────────────┬──────────────┘
                                              │ Setup Data Dict
                                              ▼
                               ┌─────────────────────────────┐
                               │   Gemini Key Manager & LLM  │
                               │   3-Key Failover Pool       │
                               │   Fallback: Local Formatter │
                               └──────────────┬──────────────┘
                                              │ Formatted Signal Text
                                              ▼
                               ┌─────────────────────────────┐
                               │     TelegramSignalBot       │
                               │  (Multicast to chat IDs)    │
                               │  (Supports SOCKS5 Proxy)    │
                               └──────────────┬──────────────┘
                                              │
                      ┌───────────────────────┴───────────────────────┐
                      ▼                                               ▼
          ┌───────────────────────┐                       ┌───────────────────────┐
          │ Telegram Chat Group   │                       │ Telegram Chat Channel │
          │ (ID: 7168024869)      │                       │ (ID: 1191689637)      │
          └───────────────────────┘                       └───────────────────────┘
```

---

## 🧩 Key Subsystems & Modules

### 1. Unified App Server (`app.py`)
- **FastAPI Core**: Serves REST endpoints (`/telegram/webhook`, `/api/webhook/tradingview`) and manages lifespan events.
- **Polling vs Webhook Dispatcher**: Checks `TELEGRAM_WEBHOOK_URL` in `.env`. Registers endpoint with Telegram if URL is set; otherwise launches `telegram_listener.py` in polling background thread.
- **Active Trade Tracker**: Maintains `active_trades` state per asset to prevent duplicate signal spamming.
- **Outcome Tracker**: Monitors active trade progress at every 3M close to detect TP1, TP2, or Stop Loss hits.

### 2. Market Data Pipeline (`core/data_fetcher.py`)
- **yfinance Primary Feed**: Fetches 15M (`5d`) and 3M (`1d`) candles directly from Yahoo Finance without API keys.
- **Cache Bypass Mechanism**: Introduces `time.sleep(random.uniform(0.5, 1.5))` and explicitly sets `ticker_obj._history = None` to prevent cross-timeframe data caching bugs.
- **Symbol Normalization**: Maps symbols (e.g. `BTC`, `BTC/USDT`, `SOL`) cleanly to Yahoo tickers (`BTC-USD`, `SOL-USD`).
- **CCXT Fallback**: Fallback layer querying Bybit/Binance if yfinance returns missing candle feeds.

### 3. SMC Strategy Engine (`core/smc_engine.py`)
- **First Line Guard**: Immediately halts evaluation if 3M volume is `0` (mid-candle scanning), returning `CANDLE_NOT_CLOSED_YET`.
- **15M Trend Detector**: Uses Market Structure (HH+HL vs LH+LL) or 50/200 EMA crossover.
- **3M Order Block Detector**: Scans last 30 candles for impulse moves exceeding $1.5 \times \text{ATR}_{3M}$ and validates non-mitigation.
- **3M FVG Detector**: Identifies 3-candle imbalance gaps and computes distance/overlap to OB zone within $1.0 \times \text{ATR}_{3M}$.
- **2-Candle Price Action Reaction**: Validates Engulfing, Rejection Wick, or OB Midpoint closes on the last 2 candles.
- **Dynamic SL / TP Ratios**:
  - Stop Loss: OB High/Low +/- ATR buffer.
  - TP1: $1:1.5$ Risk-to-Reward.
  - TP2: $1:2.5+$ Risk-to-Reward.

### 4. Gemini Key Manager & Formatter (`core/llm_signal.py`)
- **Multi-Key Pool**: Loads up to 3 Gemini API keys from `.env`.
- **Automatic Cooldown**: On `429 RESOURCE_EXHAUSTED` quota errors, blacklists the affected key for 24 hours and fails over to the next available key.
- **Local Fallback**: If all Gemini keys are on cooldown, immediately formats the signal using deterministic Python templates so signals are never lost.

### 5. Telegram Listener & UI (`bot/telegram_listener.py`)
- **Interactive Keyboard**: 6-button ReplyKeyboardMarkup grid.
- **In-Place Message Editing**: Displays `🔍 Scanning BTC/USDT...` and edits the message in-place without invalid Telegram markup parameters.
- **Diagnostic Truth Tests**: Performs full raw calculations and outputs single-column diagnostic debug reports.

---

## 🛡️ Error & Fault Tolerance Summary

| Vulnerability | Architectural Solution |
| :--- | :--- |
| **ISP Telegram API Block** | SOCKS5 proxy support via `pysocks` + Ngrok webhook mode |
| **yfinance Cache Pollution** | Micro-random sleep delays + `_history = None` reset |
| **Gemini Rate Limit (429)** | 3-Key failover pool + Instant local template fallback |
| **Telegram Edit Errors** | Clean message editing without illegal ReplyKeyboardMarkup parameters |
| **Duplicate Signal Spam** | Active trade conflict dictionary blocking new signals until trade closes |
