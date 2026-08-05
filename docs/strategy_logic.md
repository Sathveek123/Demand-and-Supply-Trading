# SMC Pullback Strategy Bot — Technical Strategy Specifications v2.1

Complete technical documentation of the Smart Money Concepts (SMC) rules, mathematical formulas, zone definitions, and validation checks.

---

## 📊 1. Mid-Candle & Volume Safety Guard

Before executing any structural calculations, `SMCEngine.analyze_setup()` inspects the latest 3M candle volume:
$$\text{Volume}_{3M} = \text{df\_3m}['\text{volume}'].\text{iloc}[-1]$$

* **If $\text{Volume}_{3M} == 0$**: The 3M candle is currently forming (mid-candle scanning). The engine immediately aborts the scan and outputs:
  `CANDLE_NOT_CLOSED_YET: Scanning mid-candle. Waiting for confirmed 3M close.`
* **If $\text{Volume}_{3M} > 0$**: The 3M candle is closed, and full structural analysis proceeds.

---

## 📈 2. 15M Higher Timeframe Trend Identification

The engine evaluates macro market structure on 15M candles:

### Primary Method: Market Structure (Swing Highs / Lows)
1. **BULLISH**:
   $$SH_1 > SH_2 \quad \text{and} \quad SL_1 > SL_2$$
   *(Consecutive Higher Highs and Higher Lows over the last 100 15M candles)*
2. **BEARISH**:
   $$SH_1 < SH_2 \quad \text{and} \quad SL_1 < SL_2$$
   *(Consecutive Lower Highs and Lower Lows)*

### Fallback Method: 20 / 50 EMA Crossover
If swing structure is range-bound or ambiguous:
- $\text{EMA}_{20} > \text{EMA}_{50} \quad \text{and} \quad \text{Close} > \text{EMA}_{20} \implies \text{BULLISH}$
- $\text{EMA}_{20} < \text{EMA}_{50} \quad \text{and} \quad \text{Close} < \text{EMA}_{20} \implies \text{BEARISH}$
- Otherwise $\implies \text{SIDEWAYS}$ *(Scan aborted — no setup)*

---

## 🧱 3. 3M Order Block (OB) Detection

Once the 15M trend is confirmed, the engine scans the **last 30 3M candles** for institutional supply/demand order blocks:

1. **Impulse Validation Threshold**:
   $$\text{Impulse Move} \ge 1.5 \times \text{ATR}_{3M}$$
2. **Bullish OB**:
   The last bearish (red) candle prior to a strong bullish impulse.
3. **Bearish OB**:
   The last bullish (green) candle prior to a strong bearish impulse.
4. **Mitigation Check (`is_ob_still_valid()`)**:
   Every OB found is tested against all subsequent candles up to the current close:
   - **Bullish OB**: If any subsequent candle closed *below* the OB Low, the zone is flagged as `OB_ALREADY_MITIGATED` and discarded.
   - **Bearish OB**: If any subsequent candle closed *above* the OB High, the zone is flagged as `OB_ALREADY_MITIGATED` and discarded.

---

## 📐 4. Fair Value Gap (FVG) & Confluence Rules

To eliminate low-accuracy setups, **an Order Block alone is insufficient**. The engine requires **FVG Confluence**:

1. **Imbalance Identification**:
   - **Bullish FVG**: $\text{Low}_{\text{Candle 3}} > \text{High}_{\text{Candle 1}}$
   - **Bearish FVG**: $\text{High}_{\text{Candle 3}} < \text{Low}_{\text{Candle 1}}$
2. **Confluence Boundary Threshold**:
   - **Overlap Check**: The FVG zone overlaps directly with the OB zone boundaries.
   - **Distance Check**: Distance between FVG and OB is less than $1.0 \times \text{ATR}_{3M}$.
3. **Verdict**: If no FVG passes the confluence check, the setup is rejected with:
   `Setup lacks FVG confluence. Order Block alone is insufficient.`

---

## ⚡ 5. 2-Candle Price Action Reaction

The engine checks the last **two 3M candles** for an active price reaction at the OB zone:

| Pattern | Definition | Confidence Level |
| :--- | :--- | :--- |
| **Engulfing Candle** | Current candle body completely covers previous opposing body | **HIGH** |
| **Wick Rejection** | Long wick in direction of zone ($\text{Wick} > 1.5 \times \text{Body}$) | **HIGH** |
| **OB Midpoint Close** | Price closes beyond $50\%$ median of OB range | **MODERATE** |
| **No Reaction** | None of the above triggers occur | **NO_CONFIRMATION (Wait)** |

---

## 🎯 6. Dynamic Risk & Reward Calculations

Parameters are computed dynamically relative to local market volatility ($\text{ATR}_{3M}$):

### Bullish Setup:
$$\text{Entry} = \text{Current 3M Close}$$
$$\text{Stop Loss (SL)} = \text{OB Low} - (0.2 \times \text{ATR}_{3M})$$
$$\text{Risk (R)} = \text{Entry} - \text{SL}$$
$$\text{TP1 (1:1.5 RR)} = \text{Entry} + (1.5 \times \text{R})$$
$$\text{TP2 (1:2.5 RR)} = \text{Entry} + (2.5 \times \text{R})$$

### Bearish Setup:
$$\text{Entry} = \text{Current 3M Close}$$
$$\text{Stop Loss (SL)} = \text{OB High} + (0.2 \times \text{ATR}_{3M})$$
$$\text{Risk (R)} = \text{SL} - \text{Entry}$$
$$\text{TP1 (1:1.5 RR)} = \text{Entry} - (1.5 \times \text{R})$$
$$\text{TP2 (1:2.5 RR)} = \text{Entry} - (2.5 \times \text{R})$$

---

## ⛔ 7. Active Trade Conflict Guard

Before broadcasting any new signal to Telegram:
1. The engine checks `active_trades[asset]`.
2. If an active trade is already open on that asset (same or opposite direction), the new setup is ignored and flagged with:
   `Active trade still running. New setup ignored until trade closes.`
3. Active trades are closed when price hits **TP1 / TP2 / SL** on subsequent 3M candle closes.
