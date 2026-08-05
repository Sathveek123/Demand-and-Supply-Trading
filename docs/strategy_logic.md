# SMC Strategy Logic — SMC Trading Bot v2.2

## 1. 15M Trend Detection
Determines direction using structural swing highs/lows combined with 20/50 EMA fallback:
- **BULLISH**: Higher Highs & Higher Lows or 20 EMA > 50 EMA.
- **BEARISH**: Lower Highs & Lower Lows or 20 EMA < 50 EMA.
- **SIDEWAYS**: Unclear trend structure (Signal generation paused).

## 2. 3M Order Block (OB) Identification
Scans the last 30 3-minute candles for strong impulse moves:
- **Impulse Threshold**: Move must be $\ge 1.5 \times \text{ATR}_{3\text{M}}$.
- **Bullish OB**: The last bearish candle before a strong bullish impulse move.
- **Bearish OB**: The last bullish candle before a strong bearish impulse move.
- **Unmitigated Validation**: Price must NOT have closed past the OB zone prior to the setup (`is_ob_still_valid`).
- **Deduplication Signature**: `ob_key` uses 5-decimal precision (`asset_direction_high:.5f_low:.5f_index`) to prevent false duplicate signals.

## 3. Fair Value Gap (FVG) Confluence
Checks for 3-candle imbalance (FVG):
- **Direct Overlap**: FVG zone intersects with the Order Block.
- **Proximity Distance**: Gap between OB and FVG must be $\le 1.3 \times \text{ATR}_{3\text{M}}$.

## 4. 3-Tier Confirmation Candle Patterns
Setup requires a 3M confirmation candle at the OB zone:
1. **Engulfing Pattern**: Current candle engulfs previous candle body.
2. **Wick Rejection**: Long rejection wick into the OB zone ($> 40\%$ of candle range).
3. **Strong Body Close / Midpoint Close**: Candle closes strongly beyond OB midpoint with volume verification.

## 5. Asset-Specific SL Buffer & Precision Math
- **Forex (EURUSD)**:
  - Fixed SL Buffer: `0.0005` (5 pips) beyond OB wick (prevents unrealistically wide stop losses).
  - Price Precision: 4 decimal places for Entry, SL, TP1, and TP2.
- **Crypto & Commodities (BTC, ETH, XAUUSD)**:
  - SL Buffer: Scaled dynamically to $\max(0.25 \times \text{ATR}_{14}, \text{Price} \times 0.0015)$.
  - Price Precision: 2 decimal places.
- **Target Math**:
  - **TP1**: Exact 1:1 Risk-to-Reward (Triggers Breakeven SL move to Entry).
  - **TP2**: Exact 1:2 Risk-to-Reward (Closes full trade position).

## 6. Asset Trading Hours Schedule
- **EURUSD**: 1:30 PM to 11:00 PM IST ONLY (Active during London & NY liquidity overlap). Paused overnight.
- **XAUUSD (GOLD)**: 9:00 AM to 11:30 PM IST ONLY (Active during metals market hours). Paused overnight.
- **BTC/USDT & ETH/USDT**: 24/7 scanning active.
