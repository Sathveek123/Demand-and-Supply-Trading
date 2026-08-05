# SMC Strategy Logic — SMC Trading Bot v2.1

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
- **Unmitigated Validation**: Price must NOT have closed past the OB zone prior to the setup.

## 3. Fair Value Gap (FVG) Confluence
Checks for 3-candle imbalance (FVG):
- **Direct Overlap**: FVG zone intersects with the Order Block.
- **Proximity Distance**: Gap between OB and FVG must be $\le 1.3 \times \text{ATR}_{3\text{M}}$.

## 4. 3-Tier Confirmation Candle Patterns
Setup requires a 3M confirmation candle at the OB zone:
1. **Engulfing Pattern**: Current candle engulfs previous candle body.
2. **Wick Rejection**: Long rejection wick into the OB zone ($> 40\%$ of candle range).
3. **Strong Body Close**: Candle closes strongly in the direction of the 15M trend.

## 5. Risk Management & Target Math
- **Entry**: Current 3M close price.
- **Stop Loss (SL)**: Set past OB High/Low with ATR-scaled buffer.
- **Take Profit 1 (TP1)**: Exact 1:1 Risk-to-Reward (Triggers Breakeven move).
- **Take Profit 2 (TP2)**: Exact 1:2 Risk-to-Reward (Closes full position).
