import logging
import time
import pandas as pd
import numpy as np
from datetime import datetime
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, ContextTypes
from config import settings
from core.smc_engine import SMCEngine
from core.data_fetcher import MarketDataFetcher
from core.llm_signal import SignalFormatter

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

fetcher = MarketDataFetcher()

def get_main_keyboard() -> ReplyKeyboardMarkup:
    """Return the persistent menu keyboard layout with 6 specified buttons."""
    keyboard = [
        [KeyboardButton("📊 BTC/USDT"), KeyboardButton("📊 ETH/USDT")],
        [KeyboardButton("📊 GOLD"), KeyboardButton("📊 EUR/USD")],
        [KeyboardButton("⚙️ STATUS"), KeyboardButton("🧪 DEBUG ALL")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True, is_persistent=True)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Register user state as ON, send welcome message and configure start menu keyboard buttons."""
    chat_id = str(update.effective_chat.id)
    from app import set_user_state
    set_user_state(chat_id, "ON")

    welcome_text = """🤖 SMC Pullback Strategy Engine v2.1

Status    : 🔍 Online — Scanning & Fetching Setups 24/7
Scanning  : BTC/USDT • ETH/USDT • XAUUSD • EURUSD
Interval  : Every 3M candle close
Data      : Live via yfinance

Signals will fire automatically whenever a valid setup is detected.

Use the buttons below or type a command.
Use /stop anytime to pause signals."""
    await update.message.reply_text(welcome_text, reply_markup=get_main_keyboard())

async def stop(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Pause signals for user by setting user state to OFF."""
    chat_id = str(update.effective_chat.id)
    from app import set_user_state
    set_user_state(chat_id, "OFF")

    paused_text = """⛔ Signals Paused

You will no longer receive auto signals.
Send /start anytime to resume."""
    await update.message.reply_text(paused_text, reply_markup=get_main_keyboard())

def normalize_asset(raw: str) -> str:
    raw = raw.upper().strip()
    if "/" not in raw:
        if raw.endswith("USDT") and len(raw) > 4:
            return raw[:-4] + "/USDT"
        elif raw.endswith("BUSD") and len(raw) > 4:
            return raw[:-4] + "/BUSD"
        elif len(raw) >= 6:
            return raw[:-3] + "/" + raw[-3:]
    return raw

async def execute_scan(update: Update, asset: str) -> None:
    """Scan asset using the SMC Engine and edit message in-place."""
    sent_msg = await update.message.reply_text(
        f"🔍 Scanning {asset}...\nFetching 15M + 3M candles. Please wait."
    )

    try:
        # Check if asset is crypto, forex, commodity or stock/index
        if any(k in asset.upper() for k in ["/", "USDT", "BTC", "ETH", "SOL", "XAU", "GOLD", "EUR"]):
            df_15m = fetcher.fetch_crypto_candles(symbol=asset, timeframe="15m", limit=100)
            time.sleep(2.0)
            df_3m = fetcher.fetch_crypto_candles(symbol=asset, timeframe="3m", limit=100)
        else:
            ticker = "^NSEI" if "NIFTY" in asset.upper() else fetcher._symbol_to_yf(asset)
            df_15m = fetcher.fetch_stock_candles(ticker=ticker, timeframe="15m", limit=100)
            time.sleep(2.0)
            df_3m = fetcher.fetch_stock_candles(ticker=ticker, timeframe="3m", limit=100)

        # Fetch live price
        live_price = None
        try:
            live_price = fetcher.fetch_live_price(asset)
        except Exception as e:
            logger.error(f"Error fetching live price for {asset}: {e}")

        # Execute SMC Strategy Engine
        analysis = SMCEngine.analyze_setup(asset_name=asset, df_15m=df_15m, df_3m=df_3m, live_price=live_price)
        formatted_msg = SignalFormatter.format_signal(analysis)

        # Edit loading message directly in-place
        await sent_msg.edit_text(formatted_msg)
        
        # If valid setup and not blocked by active signal conflict, save trade
        if analysis.get("valid"):
            from app import should_send_signal, save_active_trade, active_trades
            signal_type = analysis.get("signal_type")
            if should_send_signal(asset, signal_type):
                save_active_trade(asset, analysis)
            else:
                active_trade = active_trades.get(asset)
                active_direction = active_trade["direction"] if active_trade else "UNKNOWN"
                skip_msg = f"""⛔ {asset} — Signal Skipped
Active {active_direction} trade still running.
New {signal_type} setup ignored until trade closes."""
                await sent_msg.edit_text(skip_msg)

    except Exception as e:
        logger.error(f"Error scanning {asset}: {e}")
        try:
            await sent_msg.edit_text(f"❌ Error scanning {asset}: {e}")
        except Exception:
            pass

async def scan(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Scan asset using the SMC Engine."""
    raw_asset = context.args[0] if context.args else "BTC/USDT"
    asset = normalize_asset(raw_asset)
    await execute_scan(update, asset)

async def execute_debug(update: Update, asset: str) -> None:
    """Diagnostic validator scan for truth reporting."""
    global np, pd

    def fmt(val):
        if isinstance(val, (int, float)):
            if abs(val) < 10:
                return f"{val:,.4f}".rstrip('0').rstrip('.')
            return f"{val:,.2f}".rstrip('0').rstrip('.')
        return str(val) if val is not None else "N/A"

    # Pre-initialize default values for all diagnostic report variables
    ob_found = "NO"
    ob_high = "N/A"
    ob_low = "N/A"
    ob_type = "N/A"
    fvg_found = "NO"
    fvg_high = "N/A"
    fvg_low = "N/A"
    ob_fvg_distance = "N/A"
    confluence_valid = "NO"
    confirmation_valid = "NO"
    conf_type = "NONE"
    signal_generated = "NO"
    trend_15m = "SIDEWAYS"
    trend_method = "NONE"
    close_15m = 0.0
    close_3m = 0.0
    vol_3m = 0.0
    sh1 = 0.0
    sl1 = 0.0
    swing_range = 0.0
    atr_limit = 0.0

    loading_msg = await update.message.reply_text(
        f"🧪 SMC Diagnostic: Fetching raw calculations for {asset}..."
    )

    try:
        df_15m = fetcher.fetch_crypto_candles(symbol=asset, timeframe="15m", limit=100)
        time.sleep(2.0)
        df_3m = fetcher.fetch_crypto_candles(symbol=asset, timeframe="3m", limit=100)

        live_price = None
        try:
            live_price = fetcher.fetch_live_price(asset)
        except Exception as e:
            logger.error(f"Error fetching live price for {asset}: {e}")

        fetch_timestamp = datetime.now().strftime("%H:%M IST | %d-%m-%Y")
        
        last_15m_bar = df_15m.iloc[-1] if not df_15m.empty else None
        last_3m_bar = df_3m.iloc[-1] if not df_3m.empty else None

        trend_15m, trend_method = SMCEngine.detect_15m_trend(df_15m)
        obs = SMCEngine.find_3m_order_blocks(df_3m, trend=trend_15m)
        fvgs = SMCEngine.detect_3m_fvg(df_3m, trend=trend_15m)

        matching_obs = [ob for ob in obs if ob['type'] == trend_15m]
        active_ob = matching_obs[-1] if matching_obs else None

        ob_found = "YES" if active_ob else "NO"
        ob_high = active_ob['high'] if active_ob else "N/A"
        ob_low = active_ob['low'] if active_ob else "N/A"
        ob_type = active_ob['type'] if active_ob else "N/A"

        # Volatility ATR parameters
        high_low = df_3m['high'] - df_3m['low']
        high_close = np.abs(df_3m['high'] - df_3m['close'].shift())
        low_close = np.abs(df_3m['low'] - df_3m['close'].shift())
        ranges = pd.concat([high_low, high_close, low_close], axis=1)
        true_range = np.max(ranges, axis=1)
        atr_14 = true_range.rolling(14).mean().iloc[-1]
        if pd.isna(atr_14):
            atr_14 = (df_3m['high'] - df_3m['low']).mean()
        
        atr_limit = atr_14 * 1.3 if not pd.isna(atr_14) else 0.0

        # Check FVG
        matching_fvg = [f for f in fvgs if f['type'] == trend_15m]
        active_fvg = matching_fvg[-1] if matching_fvg else None
        fvg_found = "YES" if active_fvg else "NO"
        fvg_high = active_fvg['top'] if active_fvg else "N/A"
        fvg_low = active_fvg['bottom'] if active_fvg else "N/A"

        ob_fvg_distance = "N/A"
        confluence_valid = "NO"
        if active_ob and active_fvg:
            ob_high = active_ob.get("high", active_ob.get("top", 0.0))
            ob_low = active_ob.get("low", active_ob.get("bottom", 0.0))
            f_high = active_fvg.get("high", active_fvg.get("top", 0.0))
            f_low = active_fvg.get("low", active_fvg.get("bottom", 0.0))
            
            overlap = min(ob_high, f_high) - max(ob_low, f_low)
            if overlap > 0:
                dist = 0.0
                confluence_valid = "YES"
            else:
                ob_mid = active_ob.get("mid", (ob_high + ob_low) / 2.0)
                f_mid = active_fvg.get("mid", (f_high + f_low) / 2.0)
                dist = abs(ob_mid - f_mid)
                confluence_valid = "YES" if dist <= (atr_limit + 1e-10) else "NO"
            ob_fvg_distance = f"{fmt(dist)}"

        # Run confirmation check
        confirmation_valid = "NO"
        conf_type = "NONE"
        if active_ob:
            confirmed, conf_type = SMCEngine.check_confirmation(df_3m, trend_15m, active_ob)
            confirmation_valid = "YES" if confirmed else "NO"

        # Signal check
        analysis = SMCEngine.analyze_setup(asset_name=asset, df_15m=df_15m, df_3m=df_3m, live_price=live_price)
        signal_generated = "YES" if analysis.get("valid", False) else "NO"

        # Run Truth Test Checks
        close_15m = last_15m_bar['close'] if last_15m_bar is not None else 0.0
        close_3m = last_3m_bar['close'] if last_3m_bar is not None else 0.0
        vol_15m = last_15m_bar['volume'] if last_15m_bar is not None else 0.0
        vol_3m = last_3m_bar['volume'] if last_3m_bar is not None else 0.0

        # Calculate swing highs and lows on 15M to verify swing range and OB copying
        highs_15m = df_15m['high'].values if not df_15m.empty else []
        lows_15m = df_15m['low'].values if not df_15m.empty else []
        swing_highs = []
        swing_lows = []
        window = 5
        for i in range(window, len(df_15m) - window):
            if highs_15m[i] == max(highs_15m[i - window : i + window + 1]):
                swing_highs.append(highs_15m[i])
            if lows_15m[i] == min(lows_15m[i - window : i + window + 1]):
                swing_lows.append(lows_15m[i])

        sh1 = swing_highs[-1] if swing_highs else 0.0
        sl1 = swing_lows[-1] if swing_lows else 0.0
        swing_range = abs(sh1 - sl1) if (sh1 and sl1) else 0.0

        # Calculate dynamic swing range threshold based on 15M ATR
        high_15m_s = df_15m['high'] if not df_15m.empty else pd.Series([])
        low_15m_s = df_15m['low'] if not df_15m.empty else pd.Series([])
        close_15m_s = df_15m['close'] if not df_15m.empty else pd.Series([])
        tr_15m = pd.concat([
            high_15m_s - low_15m_s,
            (high_15m_s - close_15m_s.shift()).abs(),
            (low_15m_s - close_15m_s.shift()).abs()
        ], axis=1).max(axis=1)
        atr_15m = tr_15m.ewm(span=14, adjust=False).mean().iloc[-1] if not tr_15m.empty else 30.0
        if pd.isna(atr_15m) and not df_15m.empty:
            atr_15m = (high_15m_s - low_15m_s).mean()
        min_swing_range = 2.0 * atr_15m if (not pd.isna(atr_15m) and atr_15m > 0) else (close_15m * 0.005)

        # Sanity Checks Contract Map
        max_diff = 30 * atr_14 if not pd.isna(atr_14) else 1000.0
        checks = {
            "TF_PRICE_MATCH": abs(close_15m - close_3m) < max_diff if (close_15m and close_3m) else True,
            "VOLUME_DIFFERENT": vol_15m != vol_3m if (vol_15m and vol_3m) else True,
            "SWING_RANGE_VALID": swing_range == 0.0 or swing_range > min_swing_range,
            "ATR_REALISTIC": 0.001 < atr_14 < (close_3m * 0.1) if not pd.isna(atr_14) else True,
            "OB_NOT_SWING_COPY": active_ob is None or (
                active_ob.get("high") != sh1 and active_ob.get("low") != sl1
            )
        }

        # Determine Diagnostic Verdict
        if df_15m.empty or df_3m.empty:
            verdict = "❌ NO DATA"
            failed_checks = ["EMPTY_DATAFRAME"]
        elif vol_3m == 0:
            verdict = "⏳ CANDLE NOT CLOSED YET"
            failed_checks = ["VOLUME_ZERO"]
        elif not checks["TF_PRICE_MATCH"]:
            verdict = "❌ DATA BUG DETECTED"
            failed_checks = ["PRICE_MISMATCH"]
        elif len(df_3m) < 30:
            verdict = "FALLBACK DATA ⚠️"
            failed_checks = ["SHORT_HISTORY"]
        else:
            verdict = "✅ REAL DATA"
            failed_checks = []

        def fmt(val):
            if isinstance(val, (int, float)):
                if abs(val) < 10:
                    return f"{val:,.4f}".rstrip('0').rstrip('.')
                return f"{val:,.2f}".rstrip('0').rstrip('.')
            return str(val)

        vol_check = "✅" if vol_3m > 0 else "⏳"
        range_check = "✅" if (vol_3m > 0 and checks["SWING_RANGE_VALID"]) else ("⏳" if vol_3m == 0 else "❌")
        ob_check = "✅" if active_ob else "❌"
        fvg_check = "✅" if confluence_valid == "YES" else "❌"
        conf_check = "✅" if confirmation_valid == "YES" else "❌"

        debug_report = f"""🧪 DEBUG — {asset}
⏰ {fetch_timestamp}

📡 Data
  15M close : {fmt(close_15m)}
  3M close  : {fmt(close_3m)}
  Volume    : {fmt(vol_3m)} {vol_check}

📊 Trend (15M)
  Swing High : {fmt(sh1)}
  Swing Low  : {fmt(sl1)}
  Range      : ${fmt(swing_range)} {range_check}
  Label      : {trend_15m}

🧱 Order Block
  Found  : {ob_found}
  High   : {fmt(ob_high) if ob_high != "N/A" else "N/A"}
  Low    : {fmt(ob_low) if ob_low != "N/A" else "N/A"}
  Type   : {ob_type} {ob_check}

📐 FVG
  Found    : {fvg_found}
  Distance : {ob_fvg_distance} (threshold {fmt(atr_limit)}) {fvg_check}
  Confluence : {confluence_valid} {fvg_check}

⚡ Confirmation
  Type      : {conf_type}
  Confirmed : {confirmation_valid} {conf_check}

──────────────────────
VERDICT : {verdict}"""
        await loading_msg.edit_text(debug_report)

    except Exception as e:
        logger.error(f"Error executing debug test: {e}")
        await loading_msg.edit_text(f"❌ Diagnostic failed: {e}")

async def debug(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Diagnostic scan command router."""
    raw_asset = context.args[0] if context.args else None
    if raw_asset:
        if raw_asset.upper() in ["ALL", "EVERYTHING"]:
            await run_debug_all(update)
        else:
            asset = normalize_asset(raw_asset)
            await execute_debug(update, asset)
    else:
        await run_debug_all(update)

async def run_debug_all(update: Update) -> None:
    """Runs debug diagnostic scans on all 4 assets sequentially and replies with 4 separate messages."""
    await update.message.reply_text("🧪 Running debug on all 4 assets...")
    for asset in ["BTC/USDT", "ETH/USDT", "XAUUSD", "EURUSD"]:
        await execute_debug(update, asset)

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show active bot status metrics."""
    import time
    import pytz
    import state as bot_state
    import app as app_mod
    active_trades = getattr(app_mod, 'active_trades', {})
    start_time = getattr(app_mod, 'start_time', time.time())

    IST = pytz.timezone('Asia/Kolkata')

    uptime_seconds = int(time.time() - start_time)
    hours = uptime_seconds // 3600
    minutes = (uptime_seconds % 3600) // 60
    uptime_str = f"{hours}h {minutes}m"

    # Next scan check
    now = time.time()
    seconds_in_3m = 3 * 60
    next_scan_ts = now + (seconds_in_3m - (now % seconds_in_3m)) + 15
    next_scan_dt = datetime.fromtimestamp(next_scan_ts, IST)
    next_scan_str = next_scan_dt.strftime("%H:%M IST")

    # Use shared state singleton — reliable across threads, no import-chain races
    sched_status = "✅ Running" if bot_state.is_scheduler_alive() else "❌ Stopped"

    trades_str = ""
    for asset in settings.DEFAULT_ASSETS:
        trade = active_trades.get(asset)
        if trade:
            trades_str += f"\n  {asset:<10}: {trade['direction']} active since {trade['open_time']}"
        else:
            trades_str += f"\n  {asset:<10}: None"

    daily_results = getattr(app_mod, 'daily_results', [])

    wins = sum(1 for r in daily_results if r.get('result') == 'WIN')
    total = len(daily_results)
    win_rate_str = f"{round((wins / total) * 100, 1)}% ({wins}/{total} wins)" if total > 0 else "N/A (0 closed)"

    msg = f"""⚙️ Bot Status

Uptime      : {uptime_str}
Scheduler   : {sched_status}
Telegram    : ✅ Connected
Data feed   : ✅ yfinance live
Performance : {win_rate_str}

Active trades:{trades_str}

Next scan   : {next_scan_str}"""
    await update.message.reply_text(msg, reply_markup=get_main_keyboard())


user_last_click: dict[str, float] = {}

async def handle_all_messages(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Intercept all text messages to catch spaced/unspaced commands and reply buttons gracefully."""
    if not update.message or not update.message.text:
        return

    chat_id = str(update.effective_chat.id)
    from app import set_user_state, user_states
    if chat_id not in user_states:
        set_user_state(chat_id, "ON")

    user_state = user_states.get(chat_id, "ON")

    # Anti-Spam Guard: 3-second button cooldown per user
    now_time = time.time()
    last_click = user_last_click.get(chat_id, 0.0)
    if now_time - last_click < 3.0:
        await update.message.reply_text("⏳ Please wait 3 seconds before tapping another button.", reply_markup=get_main_keyboard())
        return
    user_last_click[chat_id] = now_time

    text = update.message.text.strip()
    
    cleaned = text
    while cleaned and not (cleaned[0].isalnum() or cleaned[0] == '/'):
        cleaned = cleaned[1:].strip()
        
    text_upper = cleaned.upper()

    # Always process /start, /stop, and /status commands regardless of OFF state
    if text_upper.startswith("/START") or text_upper == "START":
        await start(update, context)
        return
    elif text_upper.startswith("/STOP") or text_upper == "STOP":
        await stop(update, context)
        return
    elif text_upper.startswith("/STATUS") or text_upper == "STATUS" or "STATUS" in text_upper:
        await status(update, context)
        return

    # User OFF State Guard: If user turned bot OFF, block all manual scan buttons!
    if user_state == "OFF":
        msg = """🔴 Bot is currently turned OFF.

To turn the bot ON and receive live signals & manual scans:
👉 Type /start or tap START below."""
        await update.message.reply_text(msg, reply_markup=get_main_keyboard())
        return

    # Daily Rest Period Check (4 AM – 9 AM IST): Block manual scans during 5-hour maintenance rest
    import pytz
    from datetime import datetime
    IST = pytz.timezone('Asia/Kolkata')
    now_ist = datetime.now(IST)
    if 4 <= now_ist.hour < 9:
        msg = """🔴 Bot is in Daily Rest Period (4 AM – 9 AM IST).

Reason   : Daily 5-hour maintenance & liquidity sync
Scanner  : Paused ⏸️
Resumes  : 9:00 AM IST automatically ⏰"""
        await update.message.reply_text(msg, reply_markup=get_main_keyboard())
        return

    if "BTC" in text_upper and "DEBUG" not in text_upper:
        await execute_scan(update, "BTC/USDT")
    elif "ETH" in text_upper and "DEBUG" not in text_upper:
        await execute_scan(update, "ETH/USDT")
    elif ("GOLD" in text_upper or "XAU" in text_upper) and "DEBUG" not in text_upper:
        await execute_scan(update, "XAUUSD")
    elif "EUR" in text_upper and "DEBUG" not in text_upper:
        await execute_scan(update, "EURUSD")
    elif "DEBUG" in text_upper:
        if "BTC" in text_upper and "ALL" not in text_upper:
            await execute_debug(update, "BTC/USDT")
        else:
            await run_debug_all(update)
    elif text_upper.startswith("/SCAN") or text_upper.startswith("SCAN"):
        if text_upper.startswith("/SCAN"):
            raw_asset = cleaned[5:].strip()
        else:
            raw_asset = cleaned[4:].strip()
        asset = normalize_asset(raw_asset) if raw_asset else "BTC/USDT"
        await execute_scan(update, asset)
    elif text_upper.startswith("/CLEAR") or text_upper.startswith("/RESET"):
        from app import active_trades
        active_trades.clear()
        await update.message.reply_text("🔄 Active trade locks cleared. Engine is ready for fresh setup entries.", reply_markup=get_main_keyboard())
    elif text_upper.startswith("/WATCHLIST") or text_upper.startswith("WATCHLIST"):
        await watchlist(update, context)
    elif text_upper.startswith("/STATUS") or text_upper.startswith("STATUS"):
        await status(update, context)

async def watchlist(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show active watchlist assets."""
    from app import last_scan_time
    import pytz
    from datetime import datetime
    IST = pytz.timezone('Asia/Kolkata')
    last_scan_dt = datetime.fromtimestamp(last_scan_time, IST)
    last_scan_str = last_scan_dt.strftime("%H:%M IST")

    lines = ""
    for asset in settings.DEFAULT_ASSETS:
        lines += f"\n🔍 {asset:<11} — Scanning ✅"

    msg = f"""📋 Active Watchlist
{lines}

Interval : Every 3M candle close
Last scan : {last_scan_str}"""
    await update.message.reply_text(msg, reply_markup=get_main_keyboard())

def init_telegram_app() -> Application:
    """Initialize the Application instance and register command handlers."""
    from telegram.ext import MessageHandler, filters
    builder = Application.builder().token(settings.TELEGRAM_BOT_TOKEN)
    
    if settings.TELEGRAM_BASE_URL:
        builder.base_url(settings.TELEGRAM_BASE_URL)
    if settings.TELEGRAM_PROXY:
        builder.proxy(settings.TELEGRAM_PROXY)
        
    application = builder.build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("stop", stop))
    application.add_handler(CommandHandler("scan", scan))
    application.add_handler(CommandHandler("debug", debug))
    application.add_handler(CommandHandler("status", status))
    application.add_handler(CommandHandler("watchlist", watchlist))
    application.add_handler(MessageHandler(filters.TEXT, handle_all_messages))
    
    return application

async def _run_polling_async(application):
    """
    Thread-safe async polling loop.
    Uses application.initialize() + updater.start_polling() + application.start()
    instead of application.run_polling() which installs OS signal handlers
    (only allowed on the main thread — crashes on Render background threads).
    """
    import asyncio
    await application.initialize()
    await application.updater.start_polling(drop_pending_updates=True)
    await application.start()
    print("[Telegram Bot]: Polling started (thread-safe mode).")
    # Keep the loop alive indefinitely — this blocks until the task is cancelled
    try:
        while True:
            await asyncio.sleep(3600)
    except asyncio.CancelledError:
        pass
    finally:
        print("[Telegram Bot]: Stopping polling...")
        await application.updater.stop()
        await application.stop()
        await application.shutdown()


def run_telegram_listener():
    """
    Start the Telegram update polling listener.
    Uses a dedicated asyncio event loop per thread.
    Does NOT use application.run_polling() — that method installs OS signal
    handlers via set_wakeup_fd() which only works on the main OS thread,
    causing crashes when called from a daemon thread (e.g. on Render).
    """
    if not settings.TELEGRAM_BOT_TOKEN:
        print("[Telegram Bot]: Cannot run listener: No TELEGRAM_BOT_TOKEN set.")
        return

    import time
    import asyncio
    while True:
        loop = None
        try:
            print("[Telegram Bot]: Starting Event Listener...")
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            application = init_telegram_app()
            loop.run_until_complete(_run_polling_async(application))
            break  # clean exit
        except Exception as e:
            print(f"[Telegram Bot]: Connection error: {e}. Retrying listener in 10 seconds...")
            time.sleep(10)
        finally:
            if loop and not loop.is_closed():
                try:
                    loop.close()
                except Exception:
                    pass

if __name__ == "__main__":
    run_telegram_listener()

