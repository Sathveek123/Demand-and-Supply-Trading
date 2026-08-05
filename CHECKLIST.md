# SMC BOT — PRODUCTION CHECKLIST v2.1

## DATA LAYER
- `[x]` yfinance fetch uses different period per TF
  - 15M → period="5d"  interval="15m"
  - 3M  → period="2d"  interval="2m"  *(2d avoids Yahoo Finance transient 'possibly delisted' bug)*
- `[x]` random sleep 0.5–1.5s between retries (3 attempts with robust MultiIndex column flattening)
- `[x]` Ticker.history fallback if yf.download rate-limits or glitches
- `[x]` volume of last 3M candle checked FIRST (bypassed for Forex assets: EURUSD, GBPUSD)
- `[x]` ATR calculated on 3M candles only (bounded within 0.00001 to 500.0)
- `[x]` Supported Assets: `BTC/USDT`, `ETH/USDT`, `XAUUSD` (`GC=F`), `EURUSD` (`EURUSD=X`)

## SMC ENGINE & RISK
- `[x]` 15M trend detection (Composite structure + EMA crossover fallback)
- `[x]` OB detection scans LAST 30 candles (impulse threshold = 1.5 × ATR)
- `[x]` is_ob_still_valid() called on every OB (mitigated zones skipped)
- `[x]` FVG confluence threshold = 1.3 × ATR_3M (overlap checked first)
- `[x]` 3-Tier confirmation checked (Engulfing, Wick Rejection, Strong Body Close)
- `[x]` Auto-correcting TP math (1:1 RR TP1, 1:2 RR TP2)

## SCHEDULER & REPORTING
- `[x]` 24/7 scanning every 3M candle close with 20s data sync buffer
- `[x]` Operational Schedule: 9:00 AM – 4:00 AM IST (20 hours active)
- `[x]` Rest Period: 4:00 AM – 9:00 AM IST (Daily maintenance)
- `[x]` Daily Performance Report at 9:00 PM IST
- `[x]` Weekly Performance Report on Sunday 9:00 PM IST
- `[x]` Monthly Performance Report on End of Month 9:00 PM IST
- `[x]` Persistent trade history in `trade_history.json`

## TELEGRAM & USER INTERACTION
- `[x]` Persistent 6-button keyboard layout
- `[x]` Multi-user subscription registry in `users.json`
- `[x]` Multi-user broadcasting with 0.05s rate-limiting delay
- `[x]` OFF State Guard: blocks manual scans when user state is OFF
- `[x]` Anti-Spam Guard: 3-second button cooldown per user
- `[x]` Silent cloud redeploys (no false shutdown spam)
