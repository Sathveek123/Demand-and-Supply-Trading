# SMC Trading Bot v2.1 — Project Documentation

## 1. Overview
The SMC Pullback Strategy Trading Bot v2.1 is an automated trading system designed to scan cryptocurrency (`BTC/USDT`, `ETH/USDT`), commodity (`XAUUSD`), and forex (`EURUSD`) markets using Smart Money Concepts (SMC).

## 2. Core Capabilities
- **Multi-Asset SMC Scanning**: Executes technical analysis on 15-minute structural trends and 3-minute execution charts.
- **Automated Telegram Broadcasting**: Broadcasts live signals, breakeven updates, target completions, and stop-loss hits to all subscribed users.
- **Operational Schedule (9 AM – 4 AM IST)**: Operates 20 hours daily with a 5-hour maintenance rest period between 4:00 AM and 9:00 AM IST.
- **Automated Performance Reports**: Sends Daily (9 PM IST), Weekly (Sunday 9 PM IST), and Monthly (End of Month 9 PM IST) reports.
- **User Anti-Spam Safeguards**: Includes a 3-second button cooldown guard and OFF-state block to prevent Telegram API rate-limiting or user button spamming.
- **Persistent Data Tracking**: Keeps subscriptions in `users.json` and closed trade logs in `trade_history.json`.

## 3. Technology Stack
- **Language**: Python 3.11+
- **Web Framework**: FastAPI & Uvicorn
- **Telegram Library**: `python-telegram-bot` & `httpx`
- **Data Providers**: `yfinance` with fallback to `ccxt`
- **LLM Integration**: Google Gemini API via `google-genai`
- **Scheduling**: `apscheduler` and `schedule`
