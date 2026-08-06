"""
Shared bot state singleton.
Imported by both core/scheduler.py (writer) and bot/telegram_listener.py (reader).
Avoids cross-module `import app` races by keeping live state in a neutral module.
"""

import time

# Scheduler heartbeat — updated every loop cycle by TradingBotScheduler._run_loop
# Status handler reads this to confirm the scheduler is alive.
SCHEDULER_HEARTBEAT: float = 0.0   # epoch seconds; 0 = never started
SCHEDULER_STARTED: bool = False    # set True by scheduler.start()


def mark_scheduler_started() -> None:
    global SCHEDULER_STARTED, SCHEDULER_HEARTBEAT
    SCHEDULER_STARTED = True
    SCHEDULER_HEARTBEAT = time.time()


def mark_scheduler_heartbeat() -> None:
    global SCHEDULER_HEARTBEAT
    SCHEDULER_HEARTBEAT = time.time()


def is_scheduler_alive(window_seconds: int = 400) -> bool:
    """
    Returns True if the scheduler wrote a heartbeat within the last `window_seconds`.
    400s covers the worst case: 180s candle-align sleep + 20s yfinance sync + scan time.
    """
    if not SCHEDULER_STARTED:
        return False
    return (time.time() - SCHEDULER_HEARTBEAT) < window_seconds
