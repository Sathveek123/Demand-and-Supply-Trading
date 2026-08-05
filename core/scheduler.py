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
        self.last_online_date = ""
        self.last_rest_date = ""
        self.last_daily_report_date = ""
        self.last_weekly_report_date = ""
        self.last_monthly_report_date = ""

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
            from app import (
                scan_asset, check_trade_outcomes, send_daily_summary, 
                send_weekly_summary, send_monthly_summary,
                broadcast_online_status, broadcast_rest_status
            )
            import app as app_mod
            from datetime import datetime
            import pytz
            import calendar
            
            # Update last scan time
            app_mod.last_scan_time = time.time()

            IST = pytz.timezone('Asia/Kolkata')
            now_ist = datetime.now(IST)
            today_str = now_ist.strftime("%Y-%m-%d")

            # Rest period check: 4 AM to 9 AM IST (Daily maintenance & liquidity sync)
            if 4 <= now_ist.hour < 9:
                # 4:00 AM IST Rest Period Broadcast (Fires ONCE per day)
                if self.last_rest_date != today_str:
                    try:
                        broadcast_rest_status()
                        self.last_rest_date = today_str
                    except Exception as e:
                        print(f"Error broadcasting rest status: {e}")
                print(f"[SMC Scheduler]: Rest period active ({now_ist.strftime('%H:%M')} IST). Scanning paused until 9 AM IST.")
                return

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

            # Scheduled Notifications & Reports (Strict 1-Time-Per-Day Guards)
            try:
                # 9:00 AM IST Online Broadcast (Fires ONCE at 9:00 AM IST)
                if now_ist.hour == 9 and self.last_online_date != today_str:
                    broadcast_online_status()
                    self.last_online_date = today_str

                # 9:00 PM IST (21:00) Daily Summary (Fires ONCE at 9:00 PM IST)
                if now_ist.hour == 21 and self.last_daily_report_date != today_str:
                    send_daily_summary()
                    self.last_daily_report_date = today_str

                    # Sunday 9 PM IST -> Weekly 7-Day Summary
                    if now_ist.weekday() == 6 and self.last_weekly_report_date != today_str:
                        send_weekly_summary()
                        self.last_weekly_report_date = today_str

                    # Last day of month 9 PM IST -> Monthly Summary
                    last_day = calendar.monthrange(now_ist.year, now_ist.month)[1]
                    if now_ist.day == last_day and self.last_monthly_report_date != today_str:
                        send_monthly_summary()
                        self.last_monthly_report_date = today_str
            except Exception as e:
                print(f"Error running scheduled reports: {e}")

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
