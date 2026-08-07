"""
Keep-Alive Self-Pinger
======================
Render's free tier spins down any web service after 15 minutes of inactivity.
This module runs a background thread that pings the app's own public URL
every 10 minutes, which counts as HTTP traffic and prevents the spin-down.

Usage (in app.py lifespan startup):
    from core.keep_alive import start_keep_alive
    start_keep_alive()
"""

import threading
import time
import requests


_keep_alive_thread: threading.Thread | None = None
_running = False

PING_INTERVAL_SECONDS = 10 * 60   # 10 minutes — well within Render's 15-min timeout
PING_TIMEOUT_SECONDS  = 15        # Don't block longer than this on a single request


def _ping_loop(url: str) -> None:
    """Background loop: GET the app root URL every PING_INTERVAL_SECONDS."""
    global _running
    print(f"[Keep-Alive]: Pinger started. Will ping {url} every {PING_INTERVAL_SECONDS // 60} minutes.")
    while _running:
        try:
            resp = requests.get(url, timeout=PING_TIMEOUT_SECONDS)
            print(f"[Keep-Alive]: Pinged {url} → {resp.status_code}")
        except Exception as e:
            print(f"[Keep-Alive]: Ping failed (will retry next cycle): {e}")
        # Sleep in small chunks so we can exit quickly if _running is set False
        elapsed = 0
        while _running and elapsed < PING_INTERVAL_SECONDS:
            time.sleep(5)
            elapsed += 5


def start_keep_alive(url: str | None = None) -> None:
    """
    Start the keep-alive background thread.
    Call this once from the FastAPI lifespan startup block.

    Args:
        url: Full URL to ping (e.g. "https://demand-and-supply-trading.onrender.com").
             If None, reads from settings.RENDER_EXTERNAL_URL.
    """
    global _keep_alive_thread, _running

    if url is None:
        from config import settings
        url = settings.RENDER_EXTERNAL_URL.rstrip("/")

    if not url:
        print("[Keep-Alive]: No URL configured — pinger disabled.")
        return

    if _keep_alive_thread and _keep_alive_thread.is_alive():
        print("[Keep-Alive]: Pinger already running — skipping duplicate start.")
        return

    _running = True
    _keep_alive_thread = threading.Thread(
        target=_ping_loop,
        args=(url,),
        daemon=True,
        name="KeepAlivePinger"
    )
    _keep_alive_thread.start()


def stop_keep_alive() -> None:
    """Stop the keep-alive background thread cleanly."""
    global _running
    _running = False
    print("[Keep-Alive]: Pinger stopped.")
