# System Architecture — SMC Trading Bot v2.1

```
+-----------------------------------------------------------------------+
|                           SCHEDULER ENGINE                            |
|             (24/7 Scanning Every 3M Candle Close + Sync Buffer)       |
+-----------------------------------+-----------------------------------+
                                    |
                                    v
+-----------------------------------+-----------------------------------+
|                          DATA FETCHER LAYER                           |
|       (Resilient yfinance + Ticker Fallback + 15M/3M Timeframe Isolation)|
+-----------------------------------+-----------------------------------+
                                    |
                                    v
+-----------------------------------+-----------------------------------+
|                           SMC CORE ENGINE                             |
| (15M Trend + 3M OB Impulse + FVG Confluence + 3-Tier Confirmation Check)|
+-----------------------------------+-----------------------------------+
                                    |
                                    v
+-----------------------------------+-----------------------------------+
|                         SIGNAL FORMATTER LAYER                        |
|  (LLM Prompt Guard + Auto-Correcting 1:1 & 1:2 RR TP Math Generator)  |
+-----------------------------------+-----------------------------------+
                                    |
                                    v
+-----------------------------------+-----------------------------------+
|                       TELEGRAM BROADCAST LAYER                        |
|   (Multi-User Registry + 0.05s Rate Limit + 3s User Anti-Spam Guard)  |
+-----------------------------------------------------------------------+
```

## Component Architecture

1. **Market Data Fetcher (`core/data_fetcher.py`)**:
   Handles rate-limited Yahoo Finance candle extraction. Routes symbols cleanly:
   - `BTC/USDT` $\rightarrow$ `BTC-USD`
   - `ETH/USDT` $\rightarrow$ `ETH-USD`
   - `XAUUSD` $\rightarrow$ `GC=F`
   - `EURUSD` $\rightarrow$ `EURUSD=X`

2. **SMC Strategy Engine (`core/smc_engine.py`)**:
   Calculates ATR, determines composite 15M trend, detects 3M Order Blocks (`Impulse > 1.5× ATR`), validates unmitigated zones, evaluates FVG overlap/proximity ($1.3 \times \text{ATR}$), and checks 3-tier confirmation candle patterns.

3. **Signal Formatter & Key Manager (`core/llm_signal.py`)**:
   Generates institutional Telegram signal payloads. Uses Gemini LLM with automatic key rotation across 3 keys and auto-adjusts TP math to guarantee exact 1:1 and 1:2 RR.

4. **Bot Listener & State Guard (`bot/telegram_listener.py`)**:
   Handles Telegram `/start`, `/stop`, `/status`, `/scan`, and interactive keyboard buttons. Enforces a 3-second button anti-spam cooldown and blocks scans when user state is `"OFF"`.

5. **Trade Outcome & Reporting Engine (`app.py` & `core/scheduler.py`)**:
   Tracks live active positions against TP1, TP2, and SL levels. Records results in `trade_history.json` and broadcasts Daily (9 PM IST), Weekly (Sunday 9 PM IST), and Monthly performance reports.
