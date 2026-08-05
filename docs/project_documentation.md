# SMC Trading Bot v2.2 — Complete Project Documentation

## 1. Overview
The SMC Pullback Strategy Trading Bot v2.2 is an automated trading system designed to scan cryptocurrency (`BTC/USDT`, `ETH/USDT`), commodity (`XAUUSD`), and forex (`EURUSD`) markets using Smart Money Concepts (SMC).

## 2. Verified Core Capabilities
- **Multi-Asset SMC Scanning**: Scans 15-minute structural trends and 3-minute execution charts (`period='2d'` for 3M fetches).
- **Asset Trading Hours Enforcement**:
  - **EURUSD**: Active 1:30 PM to 11:00 PM IST (London/NY overlap).
  - **XAUUSD (GOLD)**: Active 9:00 AM to 11:30 PM IST (Metals market).
  - **BTC/USDT & ETH/USDT**: 24/7 scanning active.
- **5-Decimal `ob_key` Deduplication**: Unique price-level signature (`ob_key`) prevents duplicate signal broadcasts when DataFrame candle indices shift.
- **Forex Precision & Fixed SL Buffer**:
  - 4 decimal places for EURUSD Entry, SL, TP1, and TP2 (eliminates identical TP1/TP2 rounding).
  - Fixed `0.0005` (5 pips) SL buffer for EURUSD to prevent wide stop-loss zones.
- **Multi-User Telegram Broadcasting**: Broadcasts live setup signals, TP1 hit/SL to Entry updates, TP2 full target wins, and SL hit notifications to all active users (`state == "ON"`).
- **Interactive Keyboard Controls**: `/start`, `/stop`, `/status`, `/watchlist`, `/clear` commands with per-user state persistence in `users.json`.
- **Scheduled Performance Reports**: Sends Daily (9 PM IST), Weekly (Sunday 9 PM IST), and Monthly (End of Month 9 PM IST) summary reports stored in `trade_history.json`.

## 3. Technology Stack
- **Language**: Python 3.11+
- **Web Framework**: FastAPI & Uvicorn (lifespan ASGI integration)
- **Telegram Integration**: `python-telegram-bot` v20+ & `httpx`
- **Market Data**: `yfinance` with MultiIndex flattening and fallback to `ccxt`
- **LLM Integration**: Google Gemini API via `google-genai` (with local deterministic template fallback)
- **Scheduler**: Threading-based 3M candle-close boundary scheduler
