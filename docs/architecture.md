# System Architecture — SMC Trading Bot v2.2

```
+-----------------------------------------------------------------------+
|                           SCHEDULER ENGINE                            |
|        (Asset-Specific Trading Hours + 3M Candle Sync + 3.0s Delay)   |
+-----------------------------------+-----------------------------------+
                                    |
                                    v
+-----------------------------------+-----------------------------------+
|                          DATA FETCHER LAYER                           |
|       (yfinance + Ticker Fallback + MultiIndex Column Flattening)     |
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
|   (Deterministic Template / LLM Fallback + 4-Decimal Forex Precision) |
+-----------------------------------+-----------------------------------+
                                    |
                                    v
+-----------------------------------+-----------------------------------+
|                       TELEGRAM BROADCAST LAYER                        |
| (Multi-User Registry + broadcast_signal() + 5-Decimal ob_key Guard)   |
+-----------------------------------------------------------------------+
```

## Component Architecture

1. **Market Data Fetcher (`core/data_fetcher.py`)**:
   Handles Yahoo Finance candle extraction (`period='2d'` for 3M to prevent transient 'delisted' errors). Flattens MultiIndex columns and includes `Ticker.history` fallback.
   - `BTC/USDT` $\rightarrow$ `BTC-USD`
   - `ETH/USDT` $\rightarrow$ `ETH-USD`
   - `XAUUSD` $\rightarrow$ `GC=F`
   - `EURUSD` $\rightarrow$ `EURUSD=X`

2. **SMC Strategy Engine (`core/smc_engine.py`)**:
   Calculates ATR, determines composite 15M trend, detects 3M Order Blocks (`Impulse > 1.5× ATR`), validates unmitigated zones (`is_ob_still_valid`), evaluates FVG overlap/proximity ($1.3 \times \text{ATR}$), and checks 3-tier confirmation candle patterns.
   - **Forex SL Buffer**: Fixed `0.0005` (5 pips) for EURUSD to prevent wide stop losses.
   - **Forex Precision**: 4 decimal places for EURUSD prices and targets.
   - **Deduplication**: Generates 5-decimal price signature `ob_key` (`asset_direction_high:.5f_low:.5f_index`).

3. **Signal Formatter (`core/llm_signal.py`)**:
   Generates Telegram signal messages. Uses local deterministic template with fallback to Gemini LLM. Ensures TP1 is exact 1:1 RR and TP2 is exact 1:2 RR, formatted with 4 decimals for forex pairs.

4. **Bot Listener & State Guard (`bot/telegram_listener.py`)**:
   Handles Telegram `/start`, `/stop`, `/status`, `/scan`, and interactive keyboard buttons. Enforces a 3-second button anti-spam cooldown and blocks manual scans when user state is `"OFF"`.

5. **Trade Outcome & Reporting Engine (`app.py` & `core/scheduler.py`)**:
   Tracks live active positions against TP1, TP2, and SL levels. Records closed trades in `trade_history.json` and broadcasts Daily (9 PM IST), Weekly (Sunday 9 PM IST), and Monthly performance reports using `broadcast_signal()`.

6. **Asset Trading Hours (`app.py`)**:
   - **EURUSD**: Active 1:30 PM to 11:00 PM IST (London/NY overlap). Paused overnight.
   - **XAUUSD (GOLD)**: Active 9:00 AM to 11:30 PM IST (Metals market). Paused overnight.
   - **BTC/USDT & ETH/USDT**: 24/7 scanning active.
