# SMC Strategy Logic — SMC Trading Bot v2.2

This document provides the mathematical and logical specification of the Smart Money Concepts (SMC) strategy implemented in [smc_engine.py](file:///d:/Trading%20bots/Demand%20Supply%20Trading%20bot/core/smc_engine.py).

---

## 1. 15M Composite Trend Detection
Determines the higher timeframe (HTF) trend direction using a combination of structural swing highs/lows and exponential moving average (EMA) crossovers.

### A. Market Structure Trend (Swing Highs/Lows)
Scans 15-minute candles using a localized peak/trough detection window (`window = 3` candles):
- **Swing High**: A candle high that is higher than the highs of the 3 candles before and after it.
- **Swing Low**: A candle low that is lower than the lows of the 3 candles before and after it.
- **Trend Resolution**:
  - **BULLISH**: Last swing high > second-to-last swing high, AND last swing low > second-to-last swing low.
  - **BEARISH**: Last swing high < second-to-last swing high, AND last swing low < second-to-last swing low.
  - **SIDEWAYS**: Mixed or flat structure.

### B. EMA Crossover Fallback Trend
Evaluates EMA-20 and EMA-50 alignment on the 15-minute chart:
- **BULLISH**: EMA-20 > EMA-50 AND the latest candle close is above EMA-20.
- **BEARISH**: EMA-20 < EMA-50 AND the latest candle close is below EMA-20.
- **SIDEWAYS**: All other conditions.

### C. Composite Trend Resolver
Combines the Market Structure Trend and EMA Crossover Trend:
- **COMPOSITE (Bullish/Bearish)**: If both structure and EMA trends agree and are not sideways.
- **STRUCTURE (Bullish/Bearish)**: If structure trend is not sideways but differs from EMA trend.
- **EMA_FALLBACK (Bullish/Bearish)**: If structure trend is sideways but EMA trend is not.
- **SIDEWAYS**: If both trends are sideways or unclear. (Signal generation is paused).

---

## 2. BOS (Break of Structure) & Liquidity Sweep Detection
Calculates intermediate structure shifts on the 3-minute execution chart by scanning the last 10 candles (excluding the latest two, i.e., `df_3m.iloc[-10:-2]`):
- **Break of Structure (BOS)**:
  - **Bullish**: Latest candle close > maximum high of the scan range.
  - **Bearish**: Latest candle close < minimum low of the scan range.
- **Liquidity Sweep**:
  - **Bullish**: Latest candle low sweeps below the minimum low of the scan range, but the candle close remains above that minimum low.
  - **Bearish**: Latest candle high sweeps above the maximum high of the scan range, but the candle close remains below that maximum high.

---

## 3. 3M Order Block (OB) Identification & Quality Scoring
Scans the last 30 candles on the 3-minute chart for high-impulse institutional footprints:
- **Impulse Threshold**: The close-to-close difference must satisfy:
  $$\Delta \text{Close} \ge 1.5 \times \text{ATR}_{14}$$
- **Order Block Candy**:
  - **Bullish OB**: A red candle (close < open) immediately preceding a bullish impulse move.
  - **Bearish OB**: A green candle (close > open) immediately preceding a bearish impulse move.
- **Unmitigated Validation**:
  The OB zone must not have been breached by any subsequent close. A single close below the Bullish OB low or above the Bearish OB high invalidates the zone (`is_ob_still_valid`).
- **Quality Scoring**:
  $$\text{Quality Score} = \text{round}\left( \frac{\Delta\text{Close}}{\text{ATR}} \times \max(\text{Volume Ratio}, 0.5), 2 \right)$$
  Where $\text{Volume Ratio} = \text{volume}_{\text{impulse}} / \text{avg\_volume}_{30}$. OBs are sorted by Quality Score ascending, meaning the latest highest-quality OB is selected as active.
- **Deduplication Signature**:
  `ob_key` is generated as: `{asset_name}_{signal_type}_{ob_high:.5f}_{ob_low:.5f}_{active_ob_index}` to prevent duplicate signal broadcasts.

---

## 4. Fair Value Gap (FVG) Confluence
Scans the 3-minute execution chart for 3-candle structural imbalances (FVGs) where:
- **Bullish FVG**: `low[i + 2] > high[i]`. The gap size is `low[i + 2] - high[i]`.
- **Bearish FVG**: `high[i + 2] < low[i]`. The gap size is `low[i] - high[i + 2]`.
- **Confluence Distance Rule**:
  - **Direct Overlap**: If the FVG zone overlaps directly with the Order Block (overlap distance $> 0$), distance is 0.
  - **Proximity Distance**: If they do not overlap, distance is computed as:
    $$\text{Distance} = |\text{OB}_{\text{midpoint}} - \text{FVG}_{\text{midpoint}}|$$
    The setup is valid only if this distance $\le 1.3 \times \text{ATR}_{14}$.

---

## 5. 3-Tier Confirmation Candle Patterns
To trigger an entry, the latest 3M candle must tap the OB zone and produce a confirmation signature:
1. **Engulfing Pattern**:
   - **Bullish**: Current candle is green, close > previous open, and open < previous close.
   - **Bearish**: Current candle is red, close < previous open, and open > previous close.
2. **Wick Rejection**:
   - **Bullish**: Candle low taps the OB zone ($low \le OB_{high}$ and $low \ge OB_{low}$) and lower wick $> 1.5 \times$ candle body.
   - **Bearish**: Candle high taps the OB zone ($high \ge OB_{low}$ and $high \le OB_{high}$) and upper wick $> 1.5 \times$ candle body.
3. **OB Midpoint Close**:
   - Requires trading volume verification: $Volume_{\text{current}} \ge 0.8 \times AverageVolume_{10}$.
   - **Bullish**: Candle close is above the OB midpoint.
   - **Bearish**: Candle close is below the OB midpoint.

---

## 6. Dynamic Statistical Confidence Rating
Determined using a point-based scoring system (out of 12 points total) to represent setups on Telegram:

| Metric Category | Condition | Points |
| :--- | :--- | :--- |
| **Confluence Distance** | Distance $\le 0.4 \times \text{ATR}$ (Tight) | +3 |
| | Distance $\le 1.0 \times \text{ATR}$ (Standard) | +2 |
| **Confirmation Pattern** | Engulfing Pattern | +3 |
| | Wick Rejection | +2 |
| | OB Midpoint Close | +1 |
| **Trend Strength** | COMPOSITE Trend (HTF swing + EMA aligned) | +3 |
| | STRUCTURE Trend | +2 |
| | EMA Fallback Trend | +1 |
| **Market Structure Boosts**| BOS Confirmed | +2 |
| | Liquidity Swept | +1 |

### Confidence Verdicts:
- **🔥 HIGH**: Total score $\ge 8$ AND confirmation is NOT Midpoint Close.
- **⚡ MODERATE**: Total score $\ge 5$.
- **🌀 LOW**: Total score $< 5$. (LOW setups are blocked from being broadcast to Telegram).

---

## 7. Dynamic Hold Time Estimation
Hold time is dynamically estimated based on the ratio of the trade's risk (Entry to SL distance) to ATR, mapped to confirmation type:

- **Engulfing Confirmation**:
  - $\text{Risk/ATR} < 1.0$: **10–20 min**
  - $\text{Risk/ATR} < 2.0$: **20–35 min**
  - $\text{Risk/ATR} \ge 2.0$: **35–55 min**
- **Wick Rejection**:
  - $\text{Risk/ATR} < 1.0$: **15–25 min**
  - $\text{Risk/ATR} < 2.0$: **25–45 min**
  - $\text{Risk/ATR} \ge 2.0$: **45–70 min**
- **OB Midpoint Close**:
  - $\text{Risk/ATR} < 1.0$: **20–35 min**
  - $\text{Risk/ATR} < 2.0$: **35–60 min**
  - $\text{Risk/ATR} \ge 2.0$: **60–90 min**

---

## 8. Asset-Specific SL Buffer & Precision Math
Risk and target parameters adapt per asset to accommodate variance in volatility:

### A. Forex (EURUSD)
- **SL Buffer**: Fixed at `0.0005` (5 pips) beyond the OB wick boundary (prevents excessively wide stops).
- **Price Precision**: 4 decimal places for Entry, SL, TP1, and TP2.

### B. Crypto & Commodities (BTC, ETH, XAUUSD)
- **SL Buffer**: Scaled dynamically:
  $$\text{SL Buffer} = \max(0.25 \times \text{ATR}_{14}, \text{Current Price} \times 0.0015)$$
- **Price Precision**: 2 decimal places.

### C. Recommended Position Sizing
- **Recommended Units**: Calculated assuming a $10,000 account risking 1% ($100 risk per trade):
  $$\text{Units} = \frac{100.0}{\text{Entry} - \text{SL}}$$
- **Recommended Leverage**:
  $$\text{Leverage} = \min\left(10, \max\left(1, \text{round}\left( \frac{\text{Units} \times \text{Entry}}{10000.0} \right)\right)\right)$$

### D. Target Math (Risk-to-Reward)
- **TP1**: Exact 1:1 Risk-to-Reward (Triggers Breakeven SL adjustment to entry price).
- **TP2**: Exact 1:2 Risk-to-Reward (Closes the remaining position).

---

## 9. Trading Hours Schedule
To ensure the bot avoids low-liquidity periods, asset scanning is active only during specific windows:
- **EURUSD**: 1:30 PM to 11:00 PM IST (Active during London & New York liquidity overlap).
- **XAUUSD (GOLD)**: 9:00 AM to 11:30 PM IST (Active during metals market trading hours).
- **BTC/USDT & ETH/USDT**: 24/7 scanning active.
