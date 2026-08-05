import asyncio
import schedule
import time
import threading
from config import settings

class TradingBotScheduler:
    """
    Handles live scheduling and websockets to check 3M candle closes.
    Uses ccxt/websocket logic or standard polling thread to query every 3M close.
    """

    def __init__(self):
        self.running = False
        self.loop_thread = None

    def start(self):
        """
        Starts checking background thread.
        """
        self.running = True
        self.loop_thread = threading.Thread(target=self._run_loop, daemon=True)
        self.loop_thread.start()
        print("[SMC Scheduler]: Running. Checking for 3M candle closes...")

    def stop(self):
        self.running = False

    def _run_loop(self):
        # Configure job to trigger scan for all configured assets
        def job():
            from app import scan_asset, check_trade_outcomes, send_daily_summary
            import app as app_mod
            from datetime import datetime
            import pytz
            
            # Update last scan time
            app_mod.last_scan_time = time.time()

            # Check existing trades first
            try:
                check_trade_outcomes()
            except Exception as e:
                print(f"Error checking trade outcomes: {e}")

            print("[SMC Scheduler]: Periodic 3M check triggered. Scanning SMC Zones sequentially...")
            for asset in settings.DEFAULT_ASSETS:
                try:
                    scan_asset(asset=asset, send_telegram=True)
                except Exception as e:
                    print(f"[SMC Scheduler]: Error scanning {asset}: {e}")

            # Daily summary at 11:30 PM (23:30) IST
            try:
                IST = pytz.timezone('Asia/Kolkata')
                now = datetime.now(IST)
                if now.hour == 23 and now.minute == 30:
                    send_daily_summary()
            except Exception as e:
                print(f"Error sending daily summary: {e}")

        # Sync to actual candle close time (3M boundary)
        def wait_for_candle_close(timeframe_minutes=3):
            now = time.time()
            seconds_in_tf = timeframe_minutes * 60
            sleep_time = seconds_in_tf - (now % seconds_in_tf)
            print(f"[SMC Scheduler]: Aligning loop. Sleeping {round(sleep_time, 1)}s until next {timeframe_minutes}M candle close...")
            time.sleep(sleep_time)
            print("[SMC Scheduler]: Candle close boundary hit. Sleeping additional 20s for yfinance sync...")
            time.sleep(20)

        # Main execution loop
        while self.running:
            # Sync to actual 3M boundary before each scan
            wait_for_candle_close(timeframe_minutes=3)
            
            # Execute candle close check scan
            job()
            
            # Sleep 10 seconds to step past current block boundaries cleanly
            time.sleep(10)

# Start scheduler immediately if run as script
if __name__ == "__main__":
    scheduler = TradingBotScheduler()
    scheduler.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        scheduler.stop()
