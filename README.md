# SMC Pullback Strategy Trading Bot v2.1 🤖📈

An institutional-grade **Smart Money Concepts (SMC) Trading Engine** built with Python, FastAPI, and `python-telegram-bot`. Continuously monitors multi-asset price action (`BTC/USDT`, `ETH/USDT`, `XAUUSD`, `EURUSD`) on every 3-minute candle close to deliver high-probability trading signals with automated risk management and performance analytics.

---

## 🌟 Key Features

* **Multi-Asset SMC Engine**: Scans `BTC/USDT`, `ETH/USDT`, `XAUUSD` (Gold Futures `GC=F`), and `EURUSD` (`EURUSD=X`).
* **15M Trend & 3M Entry Confluence**: Identifies 15M composite structural trend and locates unmitigated 3M Order Blocks (`Impulse > 1.5× ATR`) with Fair Value Gap (FVG) overlap.
* **3-Tier Candle Confirmation**: Requires Engulfing, Wick Rejection, or Strong Body Close at OB zones before triggering signals.
* **Precision Risk Management**: Dynamic Stop Loss with ATR-scaled buffers, Take Profit 1 @ 1:1 RR (Breakeven move), and Take Profit 2 @ 2:2 RR.
* **Auto-Correcting TP Math**: Precision rounding math ensures 100% valid 1:1 and 1:2 Risk-to-Reward signals.
* **Daily Operational Schedule**: Runs 9:00 AM – 4:00 AM IST (20 hours active scanning) with a 5-hour daily maintenance rest period (4:00 AM – 9:00 AM IST).
* **Automated Performance Reports**:
  * **Daily Report**: Broadcasts every night at 9:00 PM IST (Wins, Losses, Win Rate %, Net Result points).
  * **Weekly Report**: Broadcasts every Sunday at 9:00 PM IST (7-Day Cumulative Analytics).
  * **Monthly Report**: Broadcasts on the last day of every month at 9:00 PM IST.
* **Multi-User Registry & Broadcasting**: Stores user subscriptions in `users.json` and broadcasts signals to all registered users with a `0.05s` rate-limiting safeguard.
* **User Anti-Spam Guard**: Enforces a 3-second button cooldown to prevent user spamming.
* **OFF State Guard**: Disables manual scan execution when a user turns the bot OFF (`/stop`).
* **Silent Cloud Redeploys**: Removes false offline notifications on server restarts for 100% clean deployment.

---

## 📁 Repository Structure

```
├── app.py                     # Main FastAPI application server & scanner loop
├── config.py                  # Environment settings & symbol configuration
├── requirements.txt           # Dependency manifest for Render / Cloud deploy
├── Procfile                   # Cloud process execution command
├── users.json                 # Persistent multi-user subscription registry
├── trade_history.json         # Persistent closed trade performance log
├── bot/
│   ├── telegram_bot.py        # Telegram signal broadcasting & rate-limiting client
│   └── telegram_listener.py   # Event listener, interactive keyboard & command handlers
├── core/
│   ├── data_fetcher.py        # Resilient yfinance fetcher with Ticker fallback
│   ├── smc_engine.py          # Core SMC strategy (OB, FVG, Trend, Confirmation)
│   ├── llm_signal.py          # Signal payload formatter & Gemini LLM key manager
│   └── scheduler.py           # 24/7 3M candle close scheduler & reporting engine
├── docs/                      # Architectural & strategy documentation
└── tests/                     # Unit test suite
```

---

## 🚀 Quick Setup & Deployment

### Local Setup
```bash
git clone https://github.com/Sathveek123/Demand-and-Supply-Trading.git
cd "Demand-and-Supply-Trading"
python -m venv venv
venv\Scripts\activate  # Windows
pip install -r requirements.txt
python app.py
```

### Deploy to Render
1. Create a new **Web Service** on [Render](https://render.com).
2. Connect your GitHub repository `Demand-and-Supply-Trading`.
3. Set **Build Command**: `pip install -r requirements.txt`
4. Set **Start Command**: `python app.py`
5. Add Environment Variables (`TELEGRAM_BOT_TOKEN`, `GEMINI_API_KEY`, `TELEGRAM_CHAT_IDS`).
