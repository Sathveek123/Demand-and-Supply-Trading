# SMC BOT — PRODUCTION CHECKLIST v2.2

## DATA LAYER
- `[x]` yfinance fetch uses period="2d" for 3M and period="5d" for 15M (prevents transient 'delisted' errors)
- `[x]` 3.0s delay between asset scans in scheduler loop to prevent yfinance ticker/data collisions
- `[x]` Robust MultiIndex column flattening after reset_index
- `[x]` Ticker.history fallback if yf.download rate-limits or glitches
- `[x]` Volume check on last 3M candle (bypassed for Forex assets: EURUSD, GBPUSD)
- `[x]` Supported Assets: `BTC/USDT`, `ETH/USDT`, `XAUUSD` (`GC=F`), `EURUSD` (`EURUSD=X`)

## SMC ENGINE & RISK MANAGEMENT
- `[x]` 15M trend detection (Composite structure + EMA crossover fallback)
- `[x]` OB detection scans LAST 30 candles (impulse threshold = 1.5 × ATR)
- `[x]` `is_ob_still_valid()` called on every OB (mitigated zones skipped)
- `[x]` FVG confluence threshold = 1.3 × ATR_3M (overlap checked first)
- `[x]` 3-Tier confirmation checked (Engulfing, Wick Rejection, OB Midpoint Close)
- `[x]` Forex SL Buffer: Fixed 0.0005 (5 pips) for EURUSD (prevents 100-pip wide SL zones)
- `[x]` Forex Precision: 4 decimal places for EURUSD Entry, SL, TP1, and TP2 (TP1 ≠ TP2)
- `[x]` Auto-correcting TP math (1:1 RR TP1, 1:2 RR TP2)
- `[x]` Deduplication signature: `ob_key` uses 5-decimal price boundaries (`asset_direction_high:.5f_low:.5f_index`)

## ASSET TRADING HOURS SCHEDULE
- `[x]` EURUSD Trading Hours: 1:30 PM to 11:00 PM IST ONLY (London & NY overlap). Paused overnight.
- `[x]` XAUUSD (GOLD) Trading Hours: 9:00 AM to 11:30 PM IST ONLY (Metals market). Paused overnight.
- `[x]` BTC/USDT & ETH/USDT: 24/7 scanning active.

## SCHEDULER & REPORTING
- `[x]` 3M candle close boundary alignment with 20s yfinance sync buffer
- `[x]` Top-level try/except guard in `_run_loop` so scheduler thread never crashes
- `[x]` Direct `app` module imports in `/status` handler so scheduler status reports `✅ Running` under uvicorn
- `[x]` Daily Performance Report at 9:00 PM IST
- `[x]` Weekly Performance Report on Sunday 9:00 PM IST
- `[x]` Monthly Performance Report on End of Month 9:00 PM IST
- `[x]` Persistent trade history in `trade_history.json`

## TELEGRAM & USER INTERACTION
- `[x]` Live signal format with 3-bullet Rule Checklist and Entry Zone Range
- `[x]` `broadcast_signal()` broadcasts all signals and outcomes to all active users (`state == "ON"`)
- `[x]` Persistent 6-button keyboard layout
- `[x]` Multi-user subscription registry in `users.json`
- `[x]` OFF State Guard: blocks manual scans when user state is OFF
- `[x]` Anti-Spam Guard: 3-second button cooldown per user
