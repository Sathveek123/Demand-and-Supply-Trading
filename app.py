import sys
import io
import time
from datetime import datetime
import pytz

# Force UTF-8 output — Windows defaults to cp1252 which crashes on emoji in signals/print statements
if sys.stdout.encoding != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
if sys.stderr.encoding != 'utf-8':
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

from fastapi import FastAPI, BackgroundTasks, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import asyncio
from typing import Dict, Any

from core.smc_engine import SMCEngine
from core.data_fetcher import MarketDataFetcher
from core.llm_signal import SignalFormatter
from bot.telegram_bot import TelegramSignalBot
from bot.telegram_listener import run_telegram_listener, init_telegram_app
from core.scheduler import TradingBotScheduler
from config import settings
from telegram import Update
import requests

tg_application = init_telegram_app()

app = FastAPI(title="Demand & Supply Pullback Trading Bot")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

fetcher = MarketDataFetcher()
telegram_bot = TelegramSignalBot()
scheduler = TradingBotScheduler()

IST = pytz.timezone('Asia/Kolkata')
start_time = time.time()
last_scan_time = time.time()

import json
import os

USER_FILE = "users.json"

def load_users():
    if os.path.exists(USER_FILE):
        try:
            with open(USER_FILE, "r") as f:
                return json.load(f)
        except Exception as e:
            print(f"[Users Storage]: Error reading {USER_FILE}: {e}")
    return {}

user_states = load_users()

def save_users():
    try:
        with open(USER_FILE, "w") as f:
            json.dump(user_states, f, indent=2)
    except Exception as e:
        print(f"[Users Storage]: Error saving {USER_FILE}: {e}")

def is_user_active(chat_id: str) -> bool:
    return user_states.get(str(chat_id), "ON") == "ON"

def set_user_state(chat_id: str, state: str):
    user_states[str(chat_id)] = state
    save_users()

def get_all_subscribed_users() -> list[str]:
    return list(user_states.keys())

def broadcast_signal(message: str):
    """Broadcast signal message to ALL active users who have state == 'ON'"""
    all_users = get_all_subscribed_users()
    active_users = [uid for uid in all_users if is_user_active(uid)]
    if active_users:
        telegram_bot.send_message_to_users(active_users, message)
    else:
        # Fallback if no user registered yet
        telegram_bot.send_message(message)

active_trades = {
    "BTC/USDT": None,
    "ETH/USDT": None,
    "XAUUSD": None,
    "EURUSD": None,
}

daily_results = []  # stores all closed trades for summary

@app.on_event("startup")
async def startup_event():
    # Start the live background scheduler to run check on every 3M candle close
    scheduler.start()
    
    # Broadcast Online Notification to Telegram
    assets_str = " • ".join(settings.DEFAULT_ASSETS)
    startup_msg = f"""🤖 SMC Pullback Strategy Engine v2.1

Status    : 🔍 Online — Scanning & Fetching Setups 24/7
Scanning  : {assets_str}
Interval  : Every 3M candle close
Data      : Binance via yfinance

Signals will fire automatically whenever a valid setup is detected.

Use the buttons below or type a command."""
    telegram_bot.send_message(startup_msg)
    
    # Initialize Telegram updates listener depending on TELEGRAM_WEBHOOK_URL
    if settings.TELEGRAM_WEBHOOK_URL:
        webhook_url = f"{settings.TELEGRAM_WEBHOOK_URL.rstrip('/')}/telegram/webhook"
        print(f"[Telegram Bot]: Webhook Mode enabled. Registering webhook: {webhook_url}")
        
        try:
            token = settings.TELEGRAM_BOT_TOKEN
            base_url = settings.TELEGRAM_BASE_URL.rstrip("/")
            if not (base_url.endswith("/bot") or "/bot" in base_url):
                url = f"{base_url}/bot{token}/setWebhook"
            else:
                url = f"{base_url}{token}/setWebhook" if base_url.endswith("bot") else f"{base_url}/{token}/setWebhook"
            
            proxies = None
            if settings.TELEGRAM_PROXY:
                proxies = {
                    "http": settings.TELEGRAM_PROXY,
                    "https": settings.TELEGRAM_PROXY
                }
            
            resp = requests.get(url, params={"url": webhook_url}, proxies=proxies, timeout=10)
            if resp.status_code == 200:
                print(f"[Telegram Bot]: Webhook successfully registered: {resp.json()}")
            else:
                print(f"[Telegram Bot]: Webhook registration failed ({resp.status_code}): {resp.text}")
        except Exception as e:
            print(f"[Telegram Bot]: Exception during webhook registration: {e}")
            
        await tg_application.initialize()
        await tg_application.start()
    else:
        print("[Telegram Bot]: Webhook Mode disabled. Fallback to Polling Mode.")
        import threading
        t = threading.Thread(target=run_telegram_listener, daemon=True)
        t.start()

@app.on_event("shutdown")
async def shutdown_event():
    scheduler.stop()
    
    if settings.TELEGRAM_WEBHOOK_URL:
        try:
            await tg_application.stop()
            await tg_application.shutdown()
        except Exception as e:
            print(f"[Telegram Bot]: Exception during application shutdown: {e}")
            
    # Send shutdown notification ONLY if server was up for > 10 seconds
    # (avoids sending false offline notifications on failed startup / port collision)
    if time.time() - start_time >= 10:
        shutdown_msg = """🔴 SMC Engine Going Offline

Reason  : Manual shutdown
Trades  : Close any open positions manually
Status  : Bot offline ⛔

Restart with: python app.py"""
        telegram_bot.send_message(shutdown_msg)

def should_send_signal(asset, new_direction):
    if asset not in active_trades:
        active_trades[asset] = None
    return active_trades[asset] is None

def mark_signal_active(asset, direction):
    pass

def clear_signal(asset):
    if asset in active_trades:
        active_trades[asset] = None

def save_active_trade(asset, signal):
    active_trades[asset] = {
        "direction": signal["signal_type"],
        "entry":     signal["entry"],
        "sl":        signal["stop_loss"],
        "tp1":       signal["tp1"],
        "tp2":       signal["tp2"],
        "tp1_hit":   False,
        "status":    "ACTIVE",
        "open_time": datetime.now(IST).strftime("%H:%M IST"),
    }

def check_trade_outcomes():
    for asset, trade in active_trades.items():
        if trade is None:
            continue

        live = fetcher.fetch_live_price(asset)
        if not live:
            continue

        # Sanity Guard: Ignore erratic/bad price ticks that deviate wildly from entry price
        if live < (trade["entry"] * 0.5) or live > (trade["entry"] * 2.0):
            print(f"[Outcome Checker]: Rejecting invalid/erratic price tick for {asset}: {live} (Entry: {trade['entry']})")
            continue

        direction = trade["direction"]
        result    = None

        if direction == "BUY":
            if live <= trade["sl"]:
                result = "SL_HIT"
            elif live >= trade["tp2"]:
                result = "TP2_HIT"
            elif live >= trade["tp1"] and not trade["tp1_hit"]:
                result = "TP1_HIT"

        elif direction == "SELL":
            if live >= trade["sl"]:
                result = "SL_HIT"
            elif live <= trade["tp2"]:
                result = "TP2_HIT"
            elif live <= trade["tp1"] and not trade["tp1_hit"]:
                result = "TP1_HIT"

        if result == "TP1_HIT":
            active_trades[asset]["tp1_hit"] = True
            active_trades[asset]["sl"] = trade["entry"]
            pts = round(abs(trade["tp1"] - trade["entry"]), 2)
            entry_f = f"{trade['entry']:,}".rstrip('0').rstrip('.')
            tp1_f = f"{trade['tp1']:,}".rstrip('0').rstrip('.')
            tp2_f = f"{trade['tp2']:,}".rstrip('0').rstrip('.')
            pts_f = f"{pts:,}".rstrip('0').rstrip('.')
            msg = f"""💰 TP1 HIT — {asset} 🟢

Entry was  : {entry_f}
TP1 closed : {tp1_f}
Result     : +{pts_f} pts (1:1 RR)

Move SL to entry now.
Remaining position targets TP2 → {tp2_f}"""
            telegram_bot.send_message(msg)
            print(f"[Outcome Checker]: {asset} TP1 HIT! Moved SL to entry.")

        elif result == "TP2_HIT":
            pts = round(abs(trade["tp2"] - trade["entry"]), 2)
            entry_f = f"{trade['entry']:,}".rstrip('0').rstrip('.')
            tp2_f = f"{trade['tp2']:,}".rstrip('0').rstrip('.')
            pts_f = f"{pts:,}".rstrip('0').rstrip('.')
            msg = f"""🏆 TP2 HIT — {asset} 🟢

Entry was  : {entry_f}
TP2 closed : {tp2_f}
Result     : +{pts_f} pts (1:2 RR)

Trade closed. Full target reached ✅
Next scan active 🔄"""
            telegram_bot.send_message(msg)
            daily_results.append({
                "asset": asset, "direction": direction,
                "result": "WIN", "pts": pts
            })
            active_trades[asset] = None   # clear
            print(f"[Outcome Checker]: {asset} TP2 HIT! Trade closed.")

        elif result == "SL_HIT":
            if trade["tp1_hit"]:
                pts = 0.0
                entry_f = f"{trade['entry']:,}".rstrip('0').rstrip('.')
                sl_f = f"{trade['sl']:,}".rstrip('0').rstrip('.')
                msg = f"""🛑 SL HIT — {asset} 🔴

Entry was  : {entry_f}
SL closed  : {sl_f} (Entry)
Result     : +0 pts (Breakeven)

Trade closed. Waiting for next valid setup 🔄"""
            else:
                pts = round(abs(trade["entry"] - trade["sl"]), 2)
                entry_f = f"{trade['entry']:,}".rstrip('0').rstrip('.')
                sl_f = f"{trade['sl']:,}".rstrip('0').rstrip('.')
                pts_f = f"{pts:,}".rstrip('0').rstrip('.')
                msg = f"""🛑 SL HIT — {asset} 🔴

Entry was  : {entry_f}
SL closed  : {sl_f}
Result     : -{pts_f} pts

Trade closed. Waiting for next valid setup 🔄"""
            
            telegram_bot.send_message(msg)
            daily_results.append({
                "asset": asset, "direction": direction,
                "result": "LOSS", "pts": pts if not trade["tp1_hit"] else 0.0
            })
            active_trades[asset] = None   # clear
            print(f"[Outcome Checker]: {asset} SL HIT! Trade closed.")

def send_daily_summary():
    if not daily_results:
        return

    total = len(daily_results)
    wins  = len([r for r in daily_results if r["result"] == "WIN"])
    losses= total - wins
    rate  = round((wins / total) * 100) if total > 0 else 0

    lines = ""
    for r in daily_results:
        icon = "✅" if r["result"] == "WIN" else "❌"
        sign = "+" if r["result"] == "WIN" else "-"
        outcome_lbl = "TP2" if r["result"] == "WIN" else "SL"
        pts_str = f"{r['pts']:,}".rstrip('0').rstrip('.')
        lines += f"\n{r['asset']} {r['direction']} → {outcome_lbl} {icon} {sign}{pts_str} pts"

    msg = f"""📊 Daily Summary — {datetime.now(IST).strftime('%d-%m-%Y')}

Total Signals : {total}
Wins          : {wins} ✅
Losses        : {losses} ❌
Win Rate      : {rate}%
{lines}"""

    telegram_bot.send_message(msg)
    daily_results.clear()   # reset for next day

# Cache for latest signals
latest_signals: Dict[str, Any] = {}
# Tracks last sent OB key per asset to prevent duplicate broadcasts
last_sent_signals: Dict[str, Any] = {}

@app.get("/")
def read_root():
    """
    Index endpoint returning server operational status parameters.
    """
    return {
        "status": "online",
        "bot": "SMC Pullback Strategy Engine",
        "target": "BTC/USDT",
        "channels": settings.TELEGRAM_CHAT_IDS
    }

@app.get("/api/scan")
def scan_asset(asset: str = "BTC/USDT", send_telegram: bool = True):
    """
    Runs SMC strategy analysis on any asset (15M trend + 3M OB/FVG + confirmation).
    """
    clean_asset = asset.upper().strip()
    
    # Check if asset is crypto, forex, commodity or stock/index
    if any(k in clean_asset for k in ["/", "USDT", "BTC", "ETH", "SOL", "XAU", "GOLD", "EUR"]):
        df_15m = fetcher.fetch_crypto_candles(symbol=clean_asset, timeframe="15m", limit=100)
        time.sleep(2.0)
        df_3m = fetcher.fetch_crypto_candles(symbol=clean_asset, timeframe="3m", limit=100)
    else:
        # Map ticker query cleanups
        ticker = "^NSEI" if "NIFTY" in clean_asset else fetcher._symbol_to_yf(clean_asset)
        df_15m = fetcher.fetch_stock_candles(ticker=ticker, timeframe="15m", limit=100)
        time.sleep(2.0)
        df_3m = fetcher.fetch_stock_candles(ticker=ticker, timeframe="3m", limit=100)

    # Fetch live entry price
    live_price = None
    try:
        live_price = fetcher.fetch_live_price(clean_asset)
    except Exception as e:
        print(f"Error fetching live price for {clean_asset}: {e}")

    analysis = SMCEngine.analyze_setup(asset_name=clean_asset, df_15m=df_15m, df_3m=df_3m, live_price=live_price)
    formatted_msg = SignalFormatter.format_signal(analysis)

    latest_signals[clean_asset] = {
        "analysis": analysis,
        "telegram_message": formatted_msg
    }

    if analysis.get("valid") and send_telegram:
        signal_type = analysis.get("signal_type")
        if not should_send_signal(clean_asset, signal_type):
            active_trade = active_trades.get(clean_asset)
            active_direction = active_trade["direction"] if active_trade else "UNKNOWN"
            skip_msg = f"""⛔ {clean_asset} — Signal Skipped
Active {active_direction} trade still running.
New {signal_type} setup ignored until trade closes."""
            telegram_bot.send_message(skip_msg)
            print(f"Signal blocked — {clean_asset} already in {active_direction}")
            return {
                "asset": clean_asset,
                "valid_setup": False,
                "reason": f"Signal blocked — {clean_asset} already in {active_direction}",
                "analysis": analysis,
                "telegram_message": formatted_msg
            }

        # Check duplicate setup check
        raw_ob = analysis.get("raw_ob", {})
        ob_key = (raw_ob.get("candle_index"), raw_ob.get("type"))
        
        last_sent = last_sent_signals.get(clean_asset, {})
        if last_sent.get("ob_key") == ob_key:
            print(f"[SMC Scanner]: Signal for {clean_asset} OB at {ob_key} already sent. Skipping duplicate broadcast.")
        else:
            telegram_bot.send_message(formatted_msg)
            save_active_trade(clean_asset, analysis)
            last_sent_signals[clean_asset] = {
                "ob_key": ob_key,
                "timestamp": time.time()
            }

    return {
        "asset": clean_asset,
        "valid_setup": analysis.get("valid", False),
        "analysis": analysis,
        "telegram_message": formatted_msg
    }

@app.post("/api/webhook/tradingview")
async def tradingview_webhook(request: Request):
    """
    Webhook listener for TradingView alerts.
    
    Expected Payload Formats:
    1. Direct Alert Text:
       {
         "message": "🟢 BUY SIGNAL — BTC/USDT\nEntry: 65420.5\nStop Loss: 65120.0"
       }
       
    2. Dynamic Variable Alert (Bot runs SMC calculation on trigger):
       {
         "asset": "BTC/USDT",
         "action": "BUY"
       }
    """
    try:
        payload = await request.json()
        print(f"[TradingView Webhook]: Received payload: {payload}")
        
        # Scenario 1: Pre-formatted signal message from TradingView
        if "message" in payload:
            message_text = payload["message"]
            telegram_bot.send_message(message_text)
            return {"status": "success", "message": "Pre-formatted message sent to Telegram"}
            
        # Scenario 2: Simple trigger (Bot scans chart and formats signal)
        asset = payload.get("asset", "BTC/USDT")
        res = scan_asset(asset=asset, send_telegram=True)
        return {"status": "success", "result": res}
        
    except Exception as e:
        print(f"[TradingView Webhook]: Error processing webhook: {e}")
        return JSONResponse(status_code=400, content={"status": "error", "message": str(e)})

@app.post("/telegram/webhook")
async def telegram_webhook(request: Request):
    """
    Webhook endpoint to receive updates pushed from Telegram.
    """
    if not settings.TELEGRAM_BOT_TOKEN:
        return JSONResponse(status_code=400, content={"error": "Bot token not configured"})
        
    try:
        data = await request.json()
        update = Update.de_json(data, tg_application.bot)
        await tg_application.process_update(update)
        return {"ok": True}
    except Exception as e:
        print(f"[Telegram Webhook Error]: {e}")
        return JSONResponse(status_code=500, content={"error": str(e)})

def kill_port_owner(port: int):
    import subprocess, os
    try:
        if os.name == 'nt':
            cmd = f'netstat -ano | findstr :{port}'
            out = subprocess.check_output(cmd, shell=True, text=True)
            current_pid = str(os.getpid())
            for line in out.strip().split('\n'):
                if f':{port}' in line and 'LISTENING' in line:
                    pid = line.strip().split()[-1]
                    if pid and pid != current_pid:
                        print(f"[Port Guard]: Freeing port {port} (killing process PID {pid})...")
                        subprocess.run(f'taskkill /F /PID {pid}', shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception as e:
        pass

if __name__ == "__main__":
    kill_port_owner(settings.PORT)
    import uvicorn
    uvicorn.run(app, host=settings.HOST, port=settings.PORT)
