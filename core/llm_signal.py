import json
from google import genai
from datetime import datetime
import pytz
from typing import Dict, Any, Optional
from config import settings
import time
import re

class GeminiKeyManager:
    _keys: list[str] = []
    _blacklist: dict[str, float] = {}  # key -> cooldown_until_timestamp
    _last_used: dict[str, float] = {}  # key -> last_used_timestamp

    @classmethod
    def initialize(cls):
        if not cls._keys:
            raw_keys = settings.GEMINI_API_KEY
            if not raw_keys:
                return
            parts = re.findall(r'"([^"]*)"|\'([^\']*)\'|([^,\s]+)', raw_keys.strip())
            cls._keys = [p[0] or p[1] or p[2] for p in parts if (p[0] or p[1] or p[2])]
            print(f"[Gemini Key Manager]: Loaded {len(cls._keys)} API keys.")

    @classmethod
    def get_working_key(cls) -> Optional[str]:
        cls.initialize()
        if not cls._keys:
            return None

        now = time.time()
        # Filter keys that are not blacklisted
        available_keys = []
        for key in cls._keys:
            cooldown_until = cls._blacklist.get(key, 0.0)
            if now >= cooldown_until:
                available_keys.append(key)

        if not available_keys:
            print("[Gemini Key Manager]: All API keys are currently on cooldown!")
            return None

        # Sort keys by last used time to load balance (round-robin / rate limiting)
        # Keys never used before will come first
        available_keys.sort(key=lambda k: cls._last_used.get(k, 0.0))

        selected_key = available_keys[0]
        
        # Enforce rate limiting: wait at least 4 seconds between requests on the same key (15 RPM limit)
        last_used = cls._last_used.get(selected_key, 0.0)
        time_since_last_use = now - last_used
        if time_since_last_use < 4.0:
            sleep_needed = 4.0 - time_since_last_use
            print(f"[Gemini Key Manager]: Rate limit safeguard. Sleeping {round(sleep_needed, 2)}s for key ending in ...{selected_key[-6:]}")
            time.sleep(sleep_needed)

        cls._last_used[selected_key] = time.time()
        return selected_key

    @classmethod
    def blacklist_key(cls, key: str, is_daily_quota: bool = False):
        # If daily quota limit hit, cooldown for 24 hours. Otherwise (RPM limit hit), cooldown for 1 minute.
        cooldown_duration = 24 * 3600 if is_daily_quota else 60
        cls._blacklist[key] = time.time() + cooldown_duration
        print(f"[Gemini Key Manager]: Key ending in ...{key[-6:]} blacklisted for {cooldown_duration}s.")


class SignalFormatter:
    """
    Formats trade setups into exact Telegram signal templates.
    Supports LLM formatting (Gemini / OpenAI) with direct fallback generator.
    """

    SYSTEM_PROMPT = """ROLE:
You are the SMC Pullback Strategy Signal Engine for a Telegram trading bot.
You receive structured trade data from a live scanner and output ONLY
a clean formatted Telegram message. Nothing else. No opinions. No analysis.
No extra text. Just the signal in the exact format below.

═══════════════════════════════════════
DATA VALIDATION — CHECK BEFORE OUTPUT
═══════════════════════════════════════
Before formatting any signal, validate all fields:

1. direction == "BUY"  → trend_15m must be "BULLISH"
   direction == "SELL" → trend_15m must be "BEARISH"
   Mismatch → output NULL_SIGNAL, reason: TREND_CONFLICT

2. direction == "BUY"  → sl must be BELOW entry
   direction == "SELL" → sl must be ABOVE entry
   Violation → output NULL_SIGNAL, reason: INVALID_SL

3. tp1 is 1:1 RR from entry vs sl distance. tp2 is 1:2 RR from entry vs sl distance. Auto-adjust minor rounding differences.

4. volume of last 3M candle must NOT be zero
   volume == 0 → output NULL_SIGNAL, reason: CANDLE_NOT_CLOSED

5. confidence must match setup quality:
   OB + FVG + Engulfing confirmation    → HIGH only
   OB + FVG + Wick rejection            → HIGH only
   OB + FVG + Midpoint close            → MODERATE only
   OB only  + any confirmation          → MODERATE only
   Never output HIGH for weak setups.

6. hold_time must match trade strength:
   Engulfing + risk < 1×ATR  → 10–20 min
   Engulfing + risk < 2×ATR  → 20–35 min
   Engulfing + risk > 2×ATR  → 35–55 min
   Wick rejection + risk < 1×ATR → 15–25 min
   Wick rejection + risk < 2×ATR → 25–45 min
   Wick rejection + risk > 2×ATR → 45–70 min
   Midpoint close + risk < 1×ATR → 20–35 min
   Midpoint close + risk < 2×ATR → 35–60 min
   Midpoint close + risk > 2×ATR → 60–90 min
   Never hardcode. Always calculate from risk vs ATR ratio.

═══════════════════════════════════════
OUTPUT FORMAT — BUY SIGNAL
═══════════════════════════════════════

╔══════════════════════╗
║  🟢 BUY  •  {asset}  ║
╚══════════════════════╝
⏰ {timestamp}

✅ Trend (15M)  : Bullish
🧱 Zone         : {setup_type}
⚡ Trigger      : {confirmation}

🎯 Entry  →  {entry}
🛑 SL     →  {sl}  ⬇ Below OB
💰 TP1    →  {tp1}  (1:1 RR)
💰 TP2    →  {tp2}  (1:2 RR)

⏱ Hold        : {hold_time}
📊 Confidence : {confidence}
──────────────────────
⚠️ DYOR. Not financial advice.

═══════════════════════════════════════
OUTPUT FORMAT — SELL SIGNAL
═══════════════════════════════════════

╔══════════════════════╗
║  🔴 SELL  •  {asset}  ║
╚══════════════════════╝
⏰ {timestamp}

✅ Trend (15M)  : Bearish
🧱 Zone         : {setup_type}
⚡ Trigger      : {confirmation}

🎯 Entry  →  {entry}
🛑 SL     →  {sl}  ⬆ Above OB
💰 TP1    →  {tp1}  (1:1 RR)
💰 TP2    →  {tp2}  (1:2 RR)

⏱ Hold        : {hold_time}
📊 Confidence : {confidence}
──────────────────────
⚠️ DYOR. Not financial advice.

═══════════════════════════════════════
OUTPUT FORMAT — NO SETUP
═══════════════════════════════════════

⏳ {asset} — No Setup
Reason : {reason}
Next   : 3M candle close 🔄

═══════════════════════════════════════
OUTPUT FORMAT — SIGNAL SKIPPED
═══════════════════════════════════════

⛔ {asset} — Signal Skipped
Active {direction} trade running.
New setup ignored until trade closes.

═══════════════════════════════════════
OUTPUT FORMAT — TP1 HIT
═══════════════════════════════════════

💰 TP1 HIT — {asset} 🟢
Entry  : {entry}
TP1    : {tp1}
Result : +{pts} pts ✅ (1:1 RR)

Move SL to entry now.
Riding to TP2 → {tp2} 🔄

═══════════════════════════════════════
OUTPUT FORMAT — TP2 HIT (FULL WIN)
═══════════════════════════════════════

🏆 FULL WIN — {asset} 🟢
Entry  : {entry}
TP2    : {tp2}
Result : +{pts} pts ✅ (1:2 RR)

Trade closed. Next scan active 🔄

═══════════════════════════════════════
OUTPUT FORMAT — SL HIT (LOSS)
═══════════════════════════════════════

🛑 LOSS — {asset} 🔴
Entry  : {entry}
SL     : {sl}
Result : -{pts} pts ❌

Trade closed. Waiting for next setup 🔄

═══════════════════════════════════════
OUTPUT FORMAT — DAILY SUMMARY
═══════════════════════════════════════

📊 Daily Summary — {date}

Total Signals : {total}
Wins          : {wins} ✅
Losses        : {losses} ❌
Win Rate      : {rate}%

{each_trade_result_line}

═══════════════════════════════════════
LABEL MAPPINGS
═══════════════════════════════════════
setup_type:
  "OB+FVG"  → "Order Block + FVG"
  "OB_ONLY" → "Order Block"

confirmation:
  "ENGULFING"         → "Bullish/Bearish Engulfing at OB"
  "WICK_REJECTION"    → "Strong Wick Rejection at OB"
  "OB_MIDPOINT_CLOSE" → "OB Midpoint Close"

confidence:
  "HIGH"     → "🔥 HIGH"
  "MODERATE" → "⚡ MODERATE"
  "LOW"      → never send. block the signal.

no_setup reasons:
  CANDLE_NOT_CLOSED_YET  → "Candle still forming"
  SIDEWAYS_TREND         → "15M Trend Sideways"
  NO_OB_IN_RANGE         → "No valid OB on 3M chart"
  OB_ALREADY_MITIGATED   → "OB zone already used"
  NO_FVG_CONFLUENCE      → "OB found but no FVG nearby"
  NO_CONFIRMATION        → "Waiting for confirmation candle"
  ATR_UNREALISTIC        → "Data quality issue, skipping"
"""

    @staticmethod
    def validate_llm_numbers(formatted_text: str, expected_entry: float, expected_sl: float, expected_tp1: float, expected_tp2: float) -> bool:
        """
        Validates that the LLM response text contains the exact numerical values for Entry, SL, TP1, and TP2
        (within 0.05% floating point tolerance). Returns False if LLM altered any numbers.
        """
        try:
            numbers_found = [float(n.replace(',', '')) for n in re.findall(r'\b\d+(?:\.\d+)?\b', formatted_text)]
            if not numbers_found:
                return False
            
            def contains_near(target, numbers, tol=0.0005):
                return any(abs(target - num) / target < tol for num in numbers if num > 0)

            e_ok = contains_near(expected_entry, numbers_found)
            sl_ok = contains_near(expected_sl, numbers_found)
            tp1_ok = contains_near(expected_tp1, numbers_found)
            tp2_ok = contains_near(expected_tp2, numbers_found)

            return e_ok and sl_ok and tp1_ok and tp2_ok
        except Exception:
            return False

    @staticmethod
    def format_signal(data: Dict[str, Any]) -> str:
        """
        Formats signal using either the Gemini LLM model or the structured fallback templates.
        """
        tz_ist = pytz.timezone('Asia/Kolkata')
        now_ist = datetime.now(tz_ist)
        timestamp_str = now_ist.strftime("%H:%M IST | %d-%m-%Y")

        if not data.get("valid", False):
            reason = data.get("reason", "NONE")
            clean_reason = reason.encode('ascii', 'ignore').decode('ascii')
            print(f"[SMC Engine] Scan complete. No valid setup: {clean_reason}")

            # Clean up reason label to be short and clear
            reason_lbl = reason
            if "Sideways" in reason or "unclear" in reason.lower() or "SIDEWAYS_TREND" in reason:
                reason_lbl = "15M Trend Sideways"
            elif "CANDLE_NOT_CLOSED" in reason or "mid-candle" in reason:
                reason_lbl = "Candle still forming"
            elif "No matching order block found" in reason or "No valid setup detected" in reason or "NO_OB_IN_RANGE" in reason:
                reason_lbl = "No valid OB on 3M chart"
            elif "No FVG zone detected" in reason or "confluence" in reason.lower() or "NO_FVG_CONFLUENCE" in reason:
                reason_lbl = "OB found but no FVG nearby"
            elif "No confirmation trigger detected" in reason or "trigger" in reason.lower() or "NO_CONFIRMATION" in reason:
                reason_lbl = "Waiting for confirmation candle"
            elif "OB_ALREADY_MITIGATED" in reason:
                reason_lbl = "OB zone already used"
            elif "ATR_UNREALISTIC" in reason:
                reason_lbl = "Data quality issue, skipping"

            # Use LLM formatting for No Setup if enabled and Gemini API Key is set
            if settings.USE_LLM_FORMATTER and settings.GEMINI_API_KEY:
                while True:
                    api_key = GeminiKeyManager.get_working_key()
                    if not api_key:
                        break
                    try:
                        client = genai.Client(api_key=api_key)
                        input_payload = {
                            "asset": data.get("asset", "BTC/USDT"),
                            "signal": "NONE",
                            "reason": reason_lbl,
                            "timestamp": timestamp_str
                        }
                        response = client.models.generate_content(
                            model="gemini-2.0-flash",
                            contents=f"{SignalFormatter.SYSTEM_PROMPT}\n\nFormat this signal: {json.dumps(input_payload)}"
                        )
                        return response.text.strip()
                    except Exception as e:
                        err_msg = str(e)
                        is_daily = "RESOURCE_EXHAUSTED" in err_msg or "Quota exceeded" in err_msg or "429" in err_msg
                        GeminiKeyManager.blacklist_key(api_key, is_daily_quota=is_daily)
                        print(f"[LLM Formatter]: API Key failed: {e}. Retrying next key...")

            return f"⏳ {data.get('asset', 'BTC/USDT')} — No Setup\nReason : {reason_lbl}\nNext   : 3M candle close 🔄"

        # 1. Input Contract Validation Rules
        asset = data.get("asset", "BTC/USDT")
        direction = data.get("signal_type", "BUY")  # BUY / SELL
        trend_15m = data.get("trend_15m", "BULLISH").upper()
        setup_type = "OB+FVG" if data.get("has_fvg", True) else "OB_ONLY"
        
        conf_raw = data.get("confirmation", "")
        if "Engulfing" in conf_raw:
            confirmation = "ENGULFING"
        elif "Rejection" in conf_raw:
            confirmation = "WICK_REJECTION"
        else:
            confirmation = "OB_MIDPOINT_CLOSE"

        entry = data.get("entry", 0.0)
        sl = data.get("stop_loss", 0.0)
        tp1 = data.get("tp1", 0.0)
        tp2 = data.get("tp2", 0.0)
        hold_time = data.get("hold_time", data.get("estimated_hold", "15–40 min"))
        raw_confidence = data.get("confidence", "🔥 HIGH")
        confidence = "HIGH" if "HIGH" in raw_confidence else ("MODERATE" if "MODERATE" in raw_confidence else "LOW")

        # Check Rule 1: Direction vs Trend
        if direction == "BUY" and trend_15m != "BULLISH":
            return "NULL_SIGNAL, reason: TREND_CONFLICT"
        if direction == "SELL" and trend_15m != "BEARISH":
            return "NULL_SIGNAL, reason: TREND_CONFLICT"

        # Check Rule 2: SL location
        if direction == "BUY" and sl >= entry:
            return "NULL_SIGNAL, reason: INVALID_SL"
        if direction == "SELL" and sl <= entry:
            return "NULL_SIGNAL, reason: INVALID_SL"

        # Check Rule 3: TP Math (auto-correct precision rounding to exact 1:1 and 1:2 RR)
        target_risk = abs(entry - sl)
        if target_risk > 0:
            target_tp1 = (entry + target_risk) if direction == "BUY" else (entry - target_risk)
            target_tp2 = (entry + 2.0 * target_risk) if direction == "BUY" else (entry - 2.0 * target_risk)
            dec_cnt = 4 if entry < 10 else 2
            tp1 = round(target_tp1, dec_cnt)
            tp2 = round(target_tp2, dec_cnt)

        # Check Rule 4: Volume (skip for Forex assets)
        FOREX_ASSETS = ["EURUSD", "EUR/USD", "GBPUSD", "USDJPY", "EURUSD=X", "GBPUSD=X"]
        is_forex = any(f in asset.upper() for f in FOREX_ASSETS) or ("USD" in asset.upper() and "/" not in asset.upper() and "USDT" not in asset.upper() and "XAU" not in asset.upper() and "GOLD" not in asset.upper())
        if not is_forex and (data.get("last_vol_3m", 1) == 0 or data.get("volume_3m", 1) == 0):
            return "NULL_SIGNAL, reason: CANDLE_NOT_CLOSED"

        # Check Rule 5: Confidence filter
        if confidence == "LOW":
            return "NULL_SIGNAL, reason: WEAK_CONFIDENCE"

        # Check if we should delegate signal formatting to Gemini API
        if settings.USE_LLM_FORMATTER and settings.GEMINI_API_KEY:
            while True:
                api_key = GeminiKeyManager.get_working_key()
                if not api_key:
                    break
                try:
                    client = genai.Client(api_key=api_key)
                    input_payload = {
                        "asset": asset,
                        "direction": direction,
                        "trend_15m": trend_15m,
                        "setup_type": setup_type,
                        "confirmation": confirmation,
                        "entry": entry,
                        "sl": sl,
                        "tp1": tp1,
                        "tp2": tp2,
                        "hold_time": hold_time,
                        "confidence": confidence,
                        "timestamp": timestamp_str
                    }
                    response = client.models.generate_content(
                        model="gemini-2.0-flash",
                        contents=f"{SignalFormatter.SYSTEM_PROMPT}\n\nFormat this signal: {json.dumps(input_payload)}"
                    )
                    res_text = response.text.strip()
                    if SignalFormatter.validate_llm_numbers(res_text, entry, sl, tp1, tp2):
                        return res_text
                    else:
                        print("[LLM Formatter Warning]: LLM text failed numerical validation guard. Falling back to deterministic local formatter.")
                        break
                except Exception as e:
                    err_msg = str(e)
                    is_daily = "RESOURCE_EXHAUSTED" in err_msg or "Quota exceeded" in err_msg or "429" in err_msg
                    GeminiKeyManager.blacklist_key(api_key, is_daily_quota=is_daily)
                    print(f"[LLM Formatter]: API Key failed: {e}. Retrying next key...")

        # Fallback render templates
        def get_visual_width(s):
            w = 0
            for char in s:
                if char in ["🟢", "🔴", "🔥", "⚡", "⏳", "🔄", "✅", "🧱", "🎯", "🛑", "💰", "⏱", "📊", "⚠️", "📋", "⚙️", "🧪"]:
                    w += 2
                else:
                    w += 1
            return w

        def center_line(text, target_width=22):
            vis_w = get_visual_width(text)
            padding = max(0, target_width - vis_w)
            left = padding // 2
            right = padding - left
            return " " * left + text + " " * right

        def fmt_price(val):
            if isinstance(val, (int, float)):
                return f"{val:,.2f}".rstrip('0').rstrip('.')
            return str(val)

        direction_emoji = "🟢 BUY" if direction == "BUY" else "🔴 SELL"
        trend_label     = "Bullish" if direction == "BUY" else "Bearish"
        sl_label        = "⬇ Below OB" if direction == "BUY" else "⬆ Above OB"
        
        setup_lbl = "Order Block + FVG" if setup_type == "OB+FVG" else "Order Block"
        if confirmation == "ENGULFING":
            trigger_lbl = f"{trend_label} Engulfing at OB"
        elif confirmation == "WICK_REJECTION":
            trigger_lbl = f"{trend_label} Wick Rejection at OB"
        else:
            trigger_lbl = "OB Midpoint Close"

        confidence_lbl = "🔥 HIGH" if confidence == "HIGH" else "⚡ MODERATE"

        template = f"""╔══════════════════════╗
║{center_line(f"{direction_emoji}  •  {asset}", 22)}║
╚══════════════════════╝
⏰ {timestamp_str}

✅ Trend (15M)  : {trend_label}
🧱 Zone         : {setup_lbl}
⚡ Trigger      : {trigger_lbl}

🎯 Entry  →  {fmt_price(entry)}
🛑 SL     →  {fmt_price(sl)}  {sl_label}
💰 TP1    →  {fmt_price(tp1)}  (1:1 RR)
💰 TP2    →  {fmt_price(tp2)}  (1:2 RR)

⏱ Hold        : {hold_time}
📊 Confidence : {raw_confidence}
──────────────────────
⚠️ DYOR. Not financial advice."""
        return template
