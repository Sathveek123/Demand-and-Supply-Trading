import pandas as pd
import numpy as np
from typing import Optional, Dict, Any, List

class SMCEngine:
    """
    Demand & Supply Pullback Strategy Engine (Smart Money Concepts) - Version 2.2 Release
    1. 15M Composite Trend & Structure Identification (Swing Structure + EMA Crossover)
    2. BOS (Break of Structure) & Liquidity Sweep Detection
    3. 3M Order Block (OB) Detection with Volume & Quality Scoring
    4. 3M Fair Value Gap (FVG) Imbalance & Proximity Confluence
    5. Price Action Reaction & Volume-weighted Confirmation
    6. Asset-Scaled & Volatility-Adaptive Risk Management (Dynamic SL/TP)
    7. Position Sizing & Execution Zone Calculations
    """

    @staticmethod
    def calculate_atr(df: pd.DataFrame, period: int = 14) -> Optional[float]:
        """True Range -> ATR. Returns the latest ATR value as a float."""
        high = df["high"]
        low = df["low"]
        close = df["close"]

        tr = pd.concat([
            high - low,
            (high - close.shift()).abs(),
            (low - close.shift()).abs(),
        ], axis=1).max(axis=1)

        atr = tr.ewm(span=period, adjust=False).mean()
        val = float(atr.iloc[-1])
        if pd.isna(val):
            val = float((high - low).mean())

        # Sanity check — if ATR is unrealistic for 3M, something is wrong
        if not pd.isna(val) and val > 500.0:
            print(f"[ATR WARNING] ATR={val:.2f} is unrealistic for 3M. Data may be wrong.")
            return None

        return val

    @staticmethod
    def detect_15m_trend(df_15m: pd.DataFrame, window: int = 3) -> tuple[str, str]:
        """
        Detects 15M trend based on Market Structure (Higher Highs/Lows vs Lower Highs/Lows)
        blended with EMA 20/50 alignment for fast structural identification without excessive lag.
        """
        if len(df_15m) < window * 3:
            return "SIDEWAYS", "STRUCTURE"

        highs = df_15m['high'].values
        lows = df_15m['low'].values

        swing_highs = []
        swing_lows = []

        for i in range(window, len(df_15m) - window):
            sub_highs = highs[i - window : i + window + 1]
            if highs[i] == max(sub_highs):
                swing_highs.append({"index": i, "price": float(highs[i])})

            sub_lows = lows[i - window : i + window + 1]
            if lows[i] == min(sub_lows):
                swing_lows.append({"index": i, "price": float(lows[i])})

        struct_trend = "SIDEWAYS"
        if len(swing_highs) >= 2 and len(swing_lows) >= 2:
            sh1 = swing_highs[-1]["price"]
            sh2 = swing_highs[-2]["price"]
            sl1 = swing_lows[-1]["price"]
            sl2 = swing_lows[-2]["price"]

            if sh1 > sh2 and sl1 > sl2:
                struct_trend = "BULLISH"
            elif sh1 < sh2 and sl1 < sl2:
                struct_trend = "BEARISH"

        # EMA 20 / 50 Crossover check
        ema20 = df_15m['close'].ewm(span=20, adjust=False).mean()
        ema50 = df_15m['close'].ewm(span=50, adjust=False).mean()
        last_close = float(df_15m['close'].iloc[-1])
        last_ema20 = float(ema20.iloc[-1])
        last_ema50 = float(ema50.iloc[-1])

        ema_trend = "SIDEWAYS"
        if last_ema20 > last_ema50 and last_close > last_ema20:
            ema_trend = "BULLISH"
        elif last_ema20 < last_ema50 and last_close < last_ema20:
            ema_trend = "BEARISH"

        # Composite Trend Resolver
        if struct_trend == ema_trend and struct_trend != "SIDEWAYS":
            return struct_trend, "COMPOSITE"
        elif struct_trend != "SIDEWAYS":
            return struct_trend, "STRUCTURE"
        elif ema_trend != "SIDEWAYS":
            return ema_trend, "EMA_FALLBACK"
        else:
            return "SIDEWAYS", "NONE"

    @staticmethod
    def detect_bos_and_liquidity(df_15m: pd.DataFrame, df_3m: pd.DataFrame, trend: str) -> Dict[str, Any]:
        """
        Detects Break of Structure (BOS) and Liquidity Sweeps on recent candles.
        """
        bos_confirmed = False
        liquidity_swept = False

        if len(df_3m) >= 10:
            recent_highs = df_3m['high'].iloc[-10:-2]
            recent_lows = df_3m['low'].iloc[-10:-2]
            last_close = df_3m['close'].iloc[-1]
            last_high = df_3m['high'].iloc[-1]
            last_low = df_3m['low'].iloc[-1]

            if trend == "BULLISH":
                # BOS: close above recent swing high
                if not recent_highs.empty and last_close > recent_highs.max():
                    bos_confirmed = True
                # Liquidity Sweep: wick below previous low but closed back above
                if not recent_lows.empty and last_low < recent_lows.min() and last_close > recent_lows.min():
                    liquidity_swept = True
            elif trend == "BEARISH":
                # BOS: close below recent swing low
                if not recent_lows.empty and last_close < recent_lows.min():
                    bos_confirmed = True
                # Liquidity Sweep: wick above previous high but closed back below
                if not recent_highs.empty and last_high > recent_highs.max() and last_close < recent_highs.max():
                    liquidity_swept = True

        return {
            "bos_confirmed": bos_confirmed,
            "liquidity_swept": liquidity_swept
        }

    @staticmethod
    def is_ob_still_valid(subset_df: pd.DataFrame, ob: Dict[str, Any]) -> bool:
        """
        Checks if OB zone has been breached (mitigated) by any subsequent candle.
        """
        ob_idx = ob.get("index", 0)
        ob_type = ob.get("type", "BULLISH")
        ob_high = ob.get("high", ob.get("top", 0.0))
        ob_low = ob.get("low", ob.get("bottom", 0.0))

        post_ob_candles = subset_df.iloc[ob_idx + 1:]
        if post_ob_candles.empty:
            return True

        for _, row in post_ob_candles.iterrows():
            c_close = row["close"]
            if ob_type == "BULLISH" and c_close < ob_low:
                return False
            elif ob_type == "BEARISH" and c_close > ob_high:
                return False

        return True

    @classmethod
    def find_3m_order_blocks(cls, df_3m: pd.DataFrame, trend: str = "BULLISH", atr: Optional[float] = None, lookback: int = 30) -> List[Dict[str, Any]]:
        """
        Scans last 30 candles for institutional Order Blocks.
        Ranks OB quality based on impulse expansion magnitude & volume confirmation.
        """
        obs = []
        if len(df_3m) < lookback:
            return obs

        if atr is None:
            atr = cls.calculate_atr(df_3m)

        subset = df_3m.iloc[-lookback:].copy().reset_index(drop=True)
        closes = subset["close"].values
        opens = subset["open"].values
        highs = subset["high"].values
        lows = subset["low"].values
        volumes = subset["volume"].values if "volume" in subset.columns else np.ones(len(subset))
        
        # Calculate 20-candle average volume baseline
        avg_vol = np.mean(volumes) if len(volumes) > 0 else 1.0
        impulse_threshold = 1.5 * atr

        for i in range(1, len(subset) - 1):
            move = abs(closes[i + 1] - closes[i])
            if move < impulse_threshold:
                continue

            # Volume filter — impulse candle should have healthy volume
            vol_ratio = (volumes[i + 1] / avg_vol) if avg_vol > 0 else 1.0

            # Quality Score calculation
            quality_score = round((move / atr) * max(vol_ratio, 0.5), 2)

            # Bullish OB Check (Red candle followed by strong green expansion)
            if closes[i] < opens[i] and closes[i + 1] > closes[i]:
                obs.append({
                    "type": "BULLISH",
                    "high": float(highs[i]),
                    "low": float(lows[i]),
                    "top": max(opens[i], closes[i]),
                    "bottom": float(lows[i]),
                    "mid": float((highs[i] + lows[i]) / 2),
                    "midpoint": float((highs[i] + lows[i]) / 2),
                    "candle_index": i,
                    "index": i,
                    "quality_score": quality_score
                })

            # Bearish OB Check (Green candle followed by strong red expansion)
            elif closes[i] > opens[i] and closes[i + 1] < closes[i]:
                obs.append({
                    "type": "BEARISH",
                    "high": float(highs[i]),
                    "low": float(lows[i]),
                    "top": float(highs[i]),
                    "bottom": min(opens[i], closes[i]),
                    "mid": float((highs[i] + lows[i]) / 2),
                    "midpoint": float((highs[i] + lows[i]) / 2),
                    "candle_index": i,
                    "index": i,
                    "quality_score": quality_score
                })

        # Sort OBs by quality score ascending so latest highest-quality OB is picked last
        obs.sort(key=lambda x: x["quality_score"])
        return obs

    @staticmethod
    def detect_3m_fvg(df_3m: pd.DataFrame, trend: str = "BULLISH", lookback: int = 20) -> List[Dict[str, Any]]:
        """
        Detects 3-candle Fair Value Gap (FVG) price imbalances on 3M timeframe.
        """
        fvgs = []
        if len(df_3m) < lookback:
            return fvgs

        subset = df_3m.iloc[-lookback:].copy().reset_index(drop=True)
        highs = subset["high"].values
        lows = subset["low"].values

        for i in range(len(subset) - 2):
            # Bullish FVG
            if lows[i + 2] > highs[i]:
                fvgs.append({
                    "type": "BULLISH",
                    "high": float(lows[i + 2]),
                    "low": float(highs[i]),
                    "top": float(lows[i + 2]),
                    "bottom": float(highs[i]),
                    "mid": float((lows[i + 2] + highs[i]) / 2),
                    "gap_size": float(lows[i + 2] - highs[i]),
                    "candle_index": i,
                    "index": i + 1
                })
            # Bearish FVG
            elif highs[i + 2] < lows[i]:
                fvgs.append({
                    "type": "BEARISH",
                    "high": float(lows[i]),
                    "low": float(highs[i + 2]),
                    "top": float(lows[i]),
                    "bottom": float(highs[i + 2]),
                    "mid": float((lows[i] + highs[i + 2]) / 2),
                    "gap_size": float(lows[i] - highs[i + 2]),
                    "candle_index": i,
                    "index": i + 1
                })

        return fvgs

    @staticmethod
    def check_confirmation(df_3m: pd.DataFrame, trend: str, active_ob: Dict[str, Any]) -> tuple[bool, str]:
        """
        Verifies if current candle at/near OB provides valid price action confirmation.
        """
        if len(df_3m) < 2:
            return False, "Waiting for confirmation at OB zone"

        c = df_3m.iloc[-1]
        p = df_3m.iloc[-2]

        c_body = abs(c["close"] - c["open"])
        p_body = abs(p["close"] - p["open"])

        # Volume baseline check for midpoint close
        c_vol = float(c["volume"]) if "volume" in c and not pd.isna(c["volume"]) else 1.0
        avg_vol_10 = float(df_3m["volume"].iloc[-10:].mean()) if "volume" in df_3m.columns else 1.0

        # 1. Engulfing (Strongest)
        if trend == "BULLISH":
            is_engulfing = (c["close"] > c["open"] and c["close"] > p["open"] and c["open"] < p["close"])
        else:
            is_engulfing = (c["close"] < c["open"] and c["close"] < p["open"] and c["open"] > p["close"])

        if is_engulfing:
            return True, f"{trend.capitalize()} Engulfing at OB Zone"

        # 2. Strong Wick Rejection (Strong)
        ob_high = active_ob.get("high", active_ob.get("top", 0.0))
        ob_low = active_ob.get("low", active_ob.get("bottom", 0.0))

        if trend == "BULLISH":
            lower_wick = min(c["open"], c["close"]) - c["low"]
            taps_ob = c["low"] <= ob_high and c["low"] >= ob_low
            if taps_ob and c_body > 0 and lower_wick > 1.5 * c_body:
                return True, "Bullish Wick Rejection at OB Zone"
        else:
            upper_wick = c["high"] - max(c["open"], c["close"])
            taps_ob = c["high"] >= ob_low and c["high"] <= ob_high
            if taps_ob and c_body > 0 and upper_wick > 1.5 * c_body:
                return True, "Bearish Wick Rejection at OB Zone"

        # 3. OB Midpoint Close (Requires volume verification)
        ob_mid = active_ob.get("mid", active_ob.get("midpoint", 0.0))
        if c_vol >= 0.8 * avg_vol_10:
            if trend == "BULLISH" and c["close"] > ob_mid:
                return True, "Close above OB Midpoint"
            if trend == "BEARISH" and c["close"] < ob_mid:
                return True, "Close below OB Midpoint"

        return False, "Waiting for confirmation at OB zone"

    @staticmethod
    def calculate_confidence(setup_type: str, confirmation_type: str, atr: float, fvg_distance: float, trend_method: str, bos_data: Dict[str, Any]) -> str:
        """
        Calculates dynamic statistical confidence rating (HIGH, MODERATE, LOW).
        """
        score = 0

        # Confluence distance rating
        if fvg_distance <= 0.4 * atr:      score += 3   # Very tight confluence
        elif fvg_distance <= 1.0 * atr:    score += 2   # Standard confluence

        # Confirmation quality
        if "Engulfing" in confirmation_type:     score += 3
        elif "Rejection" in confirmation_type:   score += 2
        else:                                    score += 1   # Midpoint close

        # Trend & Structure alignment
        if trend_method == "COMPOSITE":    score += 3
        elif trend_method == "STRUCTURE":  score += 2
        else:                              score += 1   # EMA fallback

        # BOS or Liquidity Sweep boost
        if bos_data.get("bos_confirmed"):   score += 2
        if bos_data.get("liquidity_swept"): score += 1

        # Rating Assignment
        if score >= 8 and "Midpoint" not in confirmation_type:
            return "🔥 HIGH"
        elif score >= 5:
            return "⚡ MODERATE"
        else:
            return "🌀 LOW"

    @staticmethod
    def calculate_hold_time(risk: float, atr: float, confirmation_type: str) -> str:
        ratio = risk / atr if atr > 0 else 1

        if "Engulfing" in confirmation_type:
            if ratio < 1:    return "10–20 min"
            elif ratio < 2:  return "20–35 min"
            else:            return "35–55 min"
        elif "Rejection" in confirmation_type:
            if ratio < 1:    return "15–25 min"
            elif ratio < 2:  return "25–45 min"
            else:            return "45–70 min"
        else:
            if ratio < 1:    return "20–35 min"
            elif ratio < 2:  return "35–60 min"
            else:            return "60–90 min"

    @classmethod
    def analyze_setup(cls, asset_name: str, df_15m: pd.DataFrame, df_3m: pd.DataFrame, sl_buffer: float = 3.0, live_price: float = None) -> Dict[str, Any]:
        """
        Runs complete SMC pipeline and outputs signal payload.
        """
        # Guard: skip if last 3M candle hasn't closed yet (volume = 0 means mid-candle on crypto/futures)
        FOREX_ASSETS = ["EURUSD", "EUR/USD", "GBPUSD", "USDJPY", "EURUSD=X", "GBPUSD=X"]
        is_forex = any(f in asset_name.upper() for f in FOREX_ASSETS) or ("USD" in asset_name.upper() and "/" not in asset_name.upper() and "USDT" not in asset_name.upper() and "XAU" not in asset_name.upper() and "GOLD" not in asset_name.upper())

        if not is_forex and not df_3m.empty and "volume" in df_3m.columns:
            total_vol = float(df_3m["volume"].sum())
            # Only apply volume check if the data feed provides volume (e.g. crypto/futures, total_vol > 0)
            if total_vol > 0:
                last_vol = df_3m["volume"].iloc[-1]
                last_vol_scalar = float(last_vol.iloc[0]) if hasattr(last_vol, 'iloc') else float(last_vol)
                print(f"[VOLUME CHECK] {asset_name} last 3M volume = {last_vol_scalar}")
                if last_vol_scalar == 0:
                    return {
                        "valid": False,
                        "reason": "⏳ CANDLE_NOT_CLOSED_YET — scanning mid-candle. Waiting for confirmed 3M close.",
                        "asset": asset_name
                    }

        trend_15m, trend_method = cls.detect_15m_trend(df_15m)
        print(f"[TREND CHECK] raw trend result = {trend_15m}, method = {trend_method}")

        if trend_15m == "SIDEWAYS":
            return {
                "valid": False,
                "reason": "⏳ 15M Trend is Sideways/Unclear. No valid setup detected. Waiting for trend clarity.",
                "asset": asset_name
            }

        atr_14 = cls.calculate_atr(df_3m)
        if atr_14 is None:
            return {
                "valid": False,
                "reason": "ATR_UNREALISTIC_DATA_BUG",
                "asset": asset_name
            }

        obs = cls.find_3m_order_blocks(df_3m, trend=trend_15m, atr=atr_14)
        fvgs = cls.detect_3m_fvg(df_3m, trend=trend_15m)
        bos_data = cls.detect_bos_and_liquidity(df_15m, df_3m, trend_15m)

        matching_obs = [ob for ob in obs if ob['type'] == trend_15m]

        if not matching_obs:
            return {
                "valid": False,
                "reason": f"⏳ 15M Trend is {trend_15m}. No valid {trend_15m} Order Block found on 3M chart.",
                "asset": asset_name,
                "trend_15m": trend_15m
            }

        # Select highest quality fresh OB
        active_ob = matching_obs[-1]

        # Check if the active OB is still valid (not mitigated)
        lookback = 30
        subset = df_3m.iloc[-lookback:].copy().reset_index(drop=True)
        if not cls.is_ob_still_valid(subset, active_ob):
            return {
                "valid": False,
                "reason": "⏳ OB_ALREADY_MITIGATED",
                "asset": asset_name,
                "trend_15m": trend_15m
            }

        # Dynamic FVG confluence limit (1.3 * ATR)
        atr_limit = atr_14 * 1.3

        has_fvg = False
        best_fvg_dist = atr_limit
        ob_mid = active_ob.get("mid", active_ob.get("midpoint", 0.0))
        ob_high = active_ob.get("high", active_ob.get("top", 0.0))
        ob_low = active_ob.get("low", active_ob.get("bottom", 0.0))

        for fvg in fvgs:
            if fvg["type"] == trend_15m:
                f_high = fvg["high"]
                f_low = fvg["low"]
                # Overlap check
                overlap = min(ob_high, f_high) - max(ob_low, f_low)
                if overlap > 0:
                    has_fvg = True
                    best_fvg_dist = 0.0
                    break
                else:
                    dist = abs(ob_mid - fvg["mid"])
                    if dist <= (atr_limit + 1e-10):
                        has_fvg = True
                        best_fvg_dist = min(best_fvg_dist, dist)

        if not has_fvg:
            return {
                "valid": False,
                "reason": "⏳ Setup lacks FVG confluence. Order Block alone is insufficient for high accuracy criteria.",
                "asset": asset_name,
                "trend_15m": trend_15m
            }

        # Check Confirmation
        confirmed, conf_type = cls.check_confirmation(df_3m, trend_15m, active_ob)

        if not confirmed:
            return {
                "valid": False,
                "reason": "⏳ Waiting for confirmation at OB zone.",
                "asset": asset_name,
                "trend_15m": trend_15m,
                "setup": "Order Block + FVG on 3M"
            }

        curr_price = df_3m['close'].iloc[-1]
        if live_price is not None and live_price > 0:
            curr_price = live_price

        # Asset-Proportional ATR Scaled Buffer (Fix for hardcoded pip buffer)
        # Scales SL buffer automatically for BTC ($63k), ETH ($1.8k), or SOL ($73)
        actual_sl_buffer = max(0.25 * atr_14, curr_price * 0.0015) if sl_buffer == 3.0 else sl_buffer

        decimals = 4 if (curr_price < 50 or "EUR" in asset_name.upper()) else 2
        if trend_15m == "BULLISH":
            signal_type = "BUY"
            sl = round(ob_low - actual_sl_buffer, decimals)
            risk = abs(curr_price - sl)
            tp1 = round(curr_price + risk, decimals)
            tp2 = round(curr_price + (2.0 * risk), decimals)
        else:
            signal_type = "SELL"
            sl = round(ob_high + actual_sl_buffer, decimals)
            risk = abs(sl - curr_price)
            tp1 = round(curr_price - risk, decimals)
            tp2 = round(curr_price - (2.0 * risk), decimals)

        # Execution Zone Range
        entry_min = round(curr_price - (0.1 * atr_14), decimals)
        entry_max = round(curr_price + (0.1 * atr_14), decimals)
        entry_zone_str = f"{entry_min} – {entry_max}"

        # Position Sizing Hint ($10,000 Account risking 1% = $100 Risk)
        risk_per_unit = max(abs(curr_price - sl), 0.0001)
        rec_units = round(100.0 / risk_per_unit, 4)
        rec_leverage = min(10, max(1, round((rec_units * curr_price) / 10000.0)))

        confidence = cls.calculate_confidence("OB+FVG", conf_type, atr_14, best_fvg_dist, trend_method, bos_data)
        hold_time = cls.calculate_hold_time(risk, atr_14, conf_type)
        
        # Unique deduplication key signature with 5 decimals for precise forex/crypto zone tracking
        ob_key = f"{asset_name}_{signal_type}_{ob_high:.5f}_{ob_low:.5f}_{active_ob.get('index', 0)}"

        return {
            "valid": True,
            "signal_type": signal_type,
            "asset": asset_name,
            "trend_15m": trend_15m,
            "trend_method": trend_method,
            "setup": "Order Block + FVG on 3M",
            "confirmation": conf_type,
            "entry": round(curr_price, decimals),
            "entry_zone": entry_zone_str,
            "stop_loss": sl,
            "tp1": tp1,
            "tp2": tp2,
            "estimated_hold": hold_time,
            "hold_time": hold_time,
            "confidence": confidence,
            "raw_ob": active_ob,
            "has_fvg": has_fvg,
            "bos_confirmed": bos_data["bos_confirmed"],
            "liquidity_swept": bos_data["liquidity_swept"],
            "rec_units": rec_units,
            "rec_leverage": rec_leverage,
            "ob_key": ob_key
        }

