# SMC BOT — PRODUCTION CHECKLIST v2.1

## DATA LAYER
- `[x]` yfinance fetch uses different period per TF
  - 15M → period="5d"  interval="15m"
  - 3M  → period="1d"  interval="2m"
- `[x]` random sleep 0.5–1.5s between TF fetches (prevents yfinance cache returning same data)
- `[x]` 15M and 3M close prices must differ (if identical → DataSanityError → abort scan)
- `[x]` volume of last 3M candle checked FIRST (volume == 0 on volume-enabled feeds → CANDLE_NOT_CLOSED_YET)
- `[x]` ATR calculated on 3M candles only (if ATR > 200 → abort scan, log ATR_UNREALISTIC)
- `[x]` live price fetched separately via fast_info (used as entry, not candle close price)
- `[x]` Supported Assets: `BTC/USDT`, `ETH/USDT`, `XAUUSD` (Gold Futures `GC=F`), `EURUSD` (`EURUSD=X`)

## SMC ENGINE
- `[x]` swing lookback = 5 candles each side minimum (swing range must be > 2 × ATR_15M, if too tight → fallback to EMA crossover)
- `[x]` OB detection scans LAST 30 candles only (not full 100 candle history)
- `[x]` OB impulse threshold = 1.5 × ATR (smaller moves do not qualify as valid OB)
- `[x]` is_ob_still_valid() called on every OB found (if any candle after OB closed beyond OB → skip)
- `[x]` FVG confluence threshold = 1.0 × ATR_3M (overlap check first, distance check second, if neither passes → NO_FVG_CONFLUENCE)
- `[x]` confirmation checked on last 2 candles only
  - engulfing → HIGH
  - wick rejection → HIGH
  - midpoint close → MODERATE
  - nothing → NO_CONFIRMATION, wait
- `[x]` confidence calculated dynamically (never hardcoded as HIGH always)
- `[x]` hold_time calculated from risk vs ATR ratio (never hardcoded as 15-40 min always)

## SIGNAL MANAGEMENT & USER SUBSCRIPTION
- `[x]` `users.json` persistent user tracking (`is_user_active`, `set_user_state`)
- `[x]` `/start` command registers user as `"ON"` and displays persistent keyboard
- `[x]` `/stop` command sets user state to `"OFF"` and pauses auto signals
- `[x]` auto signals broadcast 24/7 to all active `"ON"` users
- `[x]` active_trades dict tracking per asset (BTC/USDT, ETH/USDT, XAUUSD, EURUSD)
- `[x]` new signal blocked if same asset active
- `[x]` trade clears ONLY on TP2 hit or SL hit (TP1 hit alone does not clear trade)
- `[x]` outcome checker runs BEFORE new scan (every 3M candle close, check open trades first)
- `[x]` duplicate OB guard working (same candle_index + type = skip send)
- `[x]` daily summary sends at 11:30 PM IST (resets daily_results after sending)

## TELEGRAM DELIVERY & UI
- `[x]` 5 Persistent Reply Buttons:
  - `[📊 BTC/USDT]` `[📊 ETH/USDT]`
  - `[📊 GOLD]` `[📊 EUR/USD]`
  - `[🧪 DEBUG ALL]`
- `[x]` `🧪 DEBUG ALL` runs 4 separate diagnostic messages back-to-back
- `[x]` NO parse_mode in any send_message call (plain text only, no Markdown parse errors)
- `[x]` webhook / polling auto-failover with automatic retry wrapper

## TRUTH TEST — PASS ALL 5 TO SEND SIGNAL
- `[x]` TF_PRICE_MATCH    → diff < 30 × ATR_3M
- `[x]` VOLUME_DIFFERENT  → vol_15m != vol_3m (for crypto/futures)
- `[x]` SWING_RANGE_VALID → range > 2 × ATR_15M
- `[x]` ATR_REALISTIC     → 0.001 < ATR_3M < (close_3m * 0.1)
- `[x]` OB_NOT_SWING_COPY → ob_high != swing_high

## KNOWN NO-ACTION SITUATIONS (bot correctly silent)
- `[x]` Market ranging/sideways → no signal ✅
- `[x]` OB found but price not in zone → no signal ✅
- `[x]` OB mitigated → no signal ✅
- `[x]` Confirmation candle not formed yet → no signal ✅
- `[x]` Active trade already running → no signal ✅
- `[x]` Volume = 0 mid-candle (for crypto/futures) → no signal ✅
