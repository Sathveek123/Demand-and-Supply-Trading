# SMC Pullback Strategy Bot — Comprehensive Setup & Deployment Guide

This guide details environment configuration, user subscription tracking, Telegram proxying, ngrok webhook deployment, Gemini API key failover, and TradingView webhook integrations.

---

## 🛠️ Step-by-Step Installation & Configuration

### 1. Python Environment Setup
Ensure Python 3.10+ is installed:
```bash
python -m venv venv
.\venv\Scripts\activate   # Windows
# source venv/bin/activate # Linux/Mac

pip install -r requirements.txt
pip install pysocks requests python-telegram-bot fastapi uvicorn yfinance pandas numpy
```

---

### 2. Environment Variable Configuration (`.env`)
Create a `.env` file at the root directory of the repository:

```ini
# Primary Telegram Configuration
TELEGRAM_BOT_TOKEN=8638277068:AAH2R5nc6112doJrfRGtgYDv6qKStlPhrSY
TELEGRAM_CHAT_ID=7168024869
TELEGRAM_CHAT_IDS=7168024869,1191689637

# Multi-Key Gemini API Failover Pool (Comma Separated)
GEMINI_API_KEYS=AIzaSy...ZEsoQQ,AIzaSy...t3wfYg,AIzaSy...pVZznA

# Default Watchlist Assets
DEFAULT_ASSETS=BTC/USDT,ETH/USDT,XAUUSD,EURUSD

# Optional SOCKS5 / HTTP Proxy for Bypassing ISP Telegram Blocks
TELEGRAM_PROXY=

# Optional Base API URL Override
TELEGRAM_BASE_URL=https://api.telegram.org/bot

# Optional Webhook URL (for Ngrok / Public Server Deployment)
TELEGRAM_WEBHOOK_URL=

# Server Configuration
HOST=0.0.0.0
PORT=8000
```

---

### 3. User Subscription & State Persistence (`users.json`)

The bot tracks all Telegram users who interact with it:
- User state is stored in `users.json`.
- When a user sends `/start` or clicks any menu button, they are registered with state `"ON"`.
- When a user sends `/stop`, their state becomes `"OFF"`, pausing auto-signals for that specific user.
- The 3M scanner automatically broadcasts valid setups to all users whose state is `"ON"`.

---

### 4. Interactive Reply Keyboard Buttons

The bot displays a persistent 5-button menu layout:
```text
┌──────────────────────┬──────────────────────┐
│ 📊 BTC/USDT          │ 📊 ETH/USDT          │
├──────────────────────┼──────────────────────┤
│ 📊 GOLD              │ 📊 EUR/USD           │
├──────────────────────┴──────────────────────┤
│ 🧪 DEBUG ALL                                │
└─────────────────────────────────────────────┘
```

- **📊 BTC/USDT**, **📊 ETH/USDT**, **📊 GOLD**, **📊 EUR/USD**: Trigger manual SMC strategy scans.
- **🧪 DEBUG ALL**: Runs full truth test diagnostics across all 4 assets and returns 4 separate diagnostic messages back-to-back.
- **/stop**: Pauses auto-broadcast signals.
- **/start**: Resumes auto-broadcast signals.

---

### 5. Running the Bot Server
Launch the unified FastAPI application server:
```bash
python app.py
```

This single command initializes:
1. **FastAPI Web Server** on `http://0.0.0.0:8000`.
2. **SMC 3M Loop Scheduler** aligned to 3M candle close boundaries.
3. **Telegram Listener Thread** handling `/start`, `/stop`, `/scan`, `/debug`, and button clicks.
4. **Outcome Tracker** checking TP1/TP2/SL hits at every 3M close.

---

### 6. Automated Unit Tests & Verification
Run the engine unit test suite:
```bash
python -m unittest tests/test_smc_engine.py -v
```
