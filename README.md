# 🤖 SMC Pullback Strategy Engine v2.1

A production-grade Smart Money Concepts (SMC) Trading Engine & Telegram Bot designed for high-probability pullback entries on crypto (`BTC/USDT`, `ETH/USDT`, `SOL/USDT`) and index markets.

---

## ⚡ Core Engine Capabilities

- **15M Market Structure Context**: Automatically computes Market Structure (Higher Highs / Higher Lows for BULLISH, Lower Highs / Lower Lows for BEARISH) or 50/200 EMA trend fallback.
- **3M Order Block (OB) Detection**: Scans the last 30 3M candles for institutional supply/demand order blocks with an impulse validation threshold of $1.5 \times \text{ATR}_{3M}$.
- **Fair Value Gap (FVG) Confluence**: Validates 3M FVGs requiring overlap or distance within $1.0 \times \text{ATR}_{3M}$ of the OB zone.
- **2-Candle Price Action Confirmation**: Checks the last two 3M candles for high-confidence entry triggers (Engulfing patterns, Wick Rejection, or OB Midpoint closes).
- **Dynamic SL / TP Ratios**:
  - **SL**: Placed beyond the OB wick boundary (+ buffer).
  - **TP1**: 1:1.5 Risk-to-Reward (50% position scale out + Move SL to Breakeven).
  - **TP2**: 1:2.5+ Risk-to-Reward (Target runner).
- **Volume Mid-Candle Guard**: Automatically skips mid-candle noise if volume $= 0$, outputting `CANDLE_NOT_CLOSED_YET`.
- **yfinance Cache Bypass**: Eliminates cross-timeframe data pollution by introducing random micro-delays and clearing ticker history cache.
- **Gemini Key Manager & Failover**: Rotates up to 3 Gemini API keys with automatic cooldown on 429 quota exhaustion, falling back smoothly to local formatting.
- **Interactive Telegram Menu**: Persistent 6-button keyboard (`Scan BTC`, `Scan ETH`, `Scan SOL`, `Watchlist`, `Debug BTC`, `Status`).
- **Outcome Tracker & Daily Reports**: Monitors active trades on candle closes and dispatches daily summary reports at 23:30 IST.

---

## 🛠️ Architecture & Setup

### 1. Environment Setup
Copy `.env.example` to `.env` and configure your keys:
```ini
TELEGRAM_BOT_TOKEN=8638277068:AAH2...
TELEGRAM_CHAT_ID=7168024869
GEMINI_API_KEYS=key1,key2,key3
TELEGRAM_PROXY=
TELEGRAM_WEBHOOK_URL=
```

### 2. ISP Telegram Proxy Configuration (Optional)
If your ISP blocks `api.telegram.org`:
```bash
pip install pysocks
```
In `.env`:
```ini
TELEGRAM_PROXY=socks5://127.0.0.1:1080
```

### 3. Webhook vs Polling Mode
- **Polling Mode (Default)**: Leave `TELEGRAM_WEBHOOK_URL` empty in `.env`.
- **Webhook Mode (Production)**:
  1. Launch ngrok: `ngrok http 8000`
  2. Set `TELEGRAM_WEBHOOK_URL=https://<your-subdomain>.ngrok-free.app` in `.env`.

### 4. Run Application
```bash
python app.py
```

### 5. Run Verification Tests
```bash
python -m unittest tests/test_smc_engine.py
```

---

## 📱 Telegram Commands & Controls

| Command | Action |
| :--- | :--- |
| `/start` | Initializes interactive keyboard menu |
| `/scan BTC` | Runs SMC strategy scan on BTC/USDT |
| `/scan ETH` | Runs SMC strategy scan on ETH/USDT |
| `/scan SOL` | Runs SMC strategy scan on SOL/USDT |
| `/debug BTC` | Performs single-column raw calculation diagnostic truth test |
| `/watchlist` | Shows current market prices & 15M trend statuses |
| `/status` | Shows scheduler health, uptime, and next 3M close timer |

---

## 📄 Documentation Directory
Detailed strategy rules, architectural diagrams, and configuration guides are available in `/docs`:
- [Strategy Rules & Math](file:///d:/Trading%20bots/Demand%20Supply%20Trading%20bot/docs/strategy_logic.md)
- [System Architecture](file:///d:/Trading%20bots/Demand%20Supply%20Trading%20bot/docs/architecture.md)
- [Signal Prompt & Format](file:///d:/Trading%20bots/Demand%20Supply%20Trading%20bot/docs/signal_logic.md)
- [Setup Guide](file:///d:/Trading%20bots/Demand%20Supply%20Trading%20bot/docs/setup_guide.md)
- [Project Overview](file:///d:/Trading%20bots/Demand%20Supply%20Trading%20bot/docs/project_documentation.md)
