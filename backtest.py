"""
Backtests the SMC Pullback strategy against real historical data.

Walks forward candle-by-candle exactly as the live bot sees the market (same
rolling 100-candle window passed into SMCEngine.analyze_setup), replays the
same LOW-confidence block and one-trade-per-asset rule as app.py, and
simulates outcomes with the same TP1-moves-SL-to-breakeven / TP2 / SL logic
as app.py's check_trade_outcomes().

Limitation: Yahoo Finance only retains ~60 days of 2m/15m intraday history,
so this covers the last ~60 days, not a multi-year sample.

Run: python backtest.py
"""
import time as time_module
import pandas as pd
import yfinance as yf
from core.smc_engine import SMCEngine

ASSETS = [
    {"name": "BTC/USDT", "yf": "BTC-USD"},
    {"name": "ETH/USDT", "yf": "ETH-USD"},
    {"name": "XAUUSD",   "yf": "GC=F"},
    {"name": "EURUSD",   "yf": "EURUSD=X"},
]

WINDOW = 100  # matches limit=100 used by the live bot


def fetch_history(yf_symbol: str, interval: str, period: str) -> pd.DataFrame:
    data = yf.download(tickers=yf_symbol, period=period, interval=interval, progress=False)
    if data.empty:
        return pd.DataFrame()
    df = data.reset_index()
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = [str(c[0]).lower().strip() for c in df.columns]
    else:
        df.columns = [str(c).lower().strip() for c in df.columns]
    for ts_col in ["datetime", "date", "index"]:
        if ts_col in df.columns:
            df.rename(columns={ts_col: "timestamp"}, inplace=True)
            break
    needed = ["timestamp", "open", "high", "low", "close", "volume"]
    return df[[c for c in needed if c in df.columns]].reset_index(drop=True)


def simulate_asset(asset_cfg: dict) -> list:
    name = asset_cfg["name"]
    df_15m = fetch_history(asset_cfg["yf"], "15m", "60d")
    df_3m = fetch_history(asset_cfg["yf"], "2m", "60d")  # "2m" stands in for 3M, same as live fetcher

    if df_15m.empty or df_3m.empty or len(df_3m) < WINDOW + 10:
        print(f"  [{name}] Not enough historical data (15m={len(df_15m)}, 3m={len(df_3m)}). Skipping.")
        return []

    return simulate_from_dfs(name, df_15m, df_3m)


def simulate_from_dfs(name: str, df_15m: pd.DataFrame, df_3m: pd.DataFrame) -> list:
    trades = []
    open_trade = None

    for i in range(WINDOW, len(df_3m)):
        current_ts = df_3m.loc[i, "timestamp"]
        row = df_3m.iloc[i]

        if open_trade is not None:
            direction = open_trade["direction"]
            hi, lo = float(row["high"]), float(row["low"])
            result = None
            if direction == "BUY":
                if lo <= open_trade["sl"]:
                    result = "SL_HIT"
                elif hi >= open_trade["tp2"]:
                    result = "TP2_HIT"
                elif hi >= open_trade["tp1"] and not open_trade["tp1_hit"]:
                    result = "TP1_HIT"
            else:
                if hi >= open_trade["sl"]:
                    result = "SL_HIT"
                elif lo <= open_trade["tp2"]:
                    result = "TP2_HIT"
                elif lo <= open_trade["tp1"] and not open_trade["tp1_hit"]:
                    result = "TP1_HIT"

            if result == "TP1_HIT":
                open_trade["tp1_hit"] = True
                open_trade["sl"] = open_trade["entry"]  # breakeven, matches live
            elif result == "TP2_HIT":
                open_trade["exit_r"] = 2.0
                open_trade["close_ts"] = current_ts
                trades.append(open_trade)
                open_trade = None
            elif result == "SL_HIT":
                open_trade["exit_r"] = 0.0 if open_trade["tp1_hit"] else -1.0
                open_trade["close_ts"] = current_ts
                trades.append(open_trade)
                open_trade = None

        if open_trade is not None:
            continue  # one trade per asset at a time, same as should_send_signal()

        window_3m = df_3m.iloc[i - WINDOW + 1:i + 1].reset_index(drop=True)
        window_15m = df_15m[df_15m["timestamp"] <= current_ts].tail(WINDOW)
        if len(window_15m) < 20:
            continue

        try:
            analysis = SMCEngine.analyze_setup(asset_name=name, df_15m=window_15m, df_3m=window_3m)
        except Exception:
            continue

        if not analysis.get("valid"):
            continue
        if "LOW" in analysis.get("confidence", ""):
            continue  # live code never broadcasts LOW-confidence signals

        open_trade = {
            "asset": name,
            "direction": analysis["signal_type"],
            "entry": analysis["entry"],
            "sl": analysis["stop_loss"],
            "tp1": analysis["tp1"],
            "tp2": analysis["tp2"],
            "confidence": analysis["confidence"],
            "tp1_hit": False,
            "open_ts": current_ts,
        }

    return trades


def report(all_trades: list):
    if not all_trades:
        print("\nNo trades were generated across the backtest window.")
        return

    print("\n" + "=" * 60)
    print("BACKTEST RESULTS — SMC Pullback Strategy (~60 days)")
    print("=" * 60)

    by_asset = {}
    for t in all_trades:
        by_asset.setdefault(t["asset"], []).append(t)

    total_trades = 0
    total_wins = 0
    total_r = 0.0

    for asset, trades in by_asset.items():
        rs = [t["exit_r"] for t in trades]
        wins = sum(1 for r in rs if r > 0)
        losses = sum(1 for r in rs if r < 0)
        breakeven = sum(1 for r in rs if r == 0)
        win_rate = (wins / len(rs) * 100) if rs else 0.0
        avg_r = (sum(rs) / len(rs)) if rs else 0.0

        print(f"\n{asset}")
        print(f"  Trades      : {len(rs)}")
        print(f"  Wins/Losses/BE : {wins}/{losses}/{breakeven}")
        print(f"  Win rate    : {win_rate:.1f}%")
        print(f"  Avg R       : {avg_r:+.2f}R")
        print(f"  Total R     : {sum(rs):+.2f}R")

        total_trades += len(rs)
        total_wins += wins
        total_r += sum(rs)

    all_sorted = sorted(all_trades, key=lambda t: t["open_ts"])
    running = 0.0
    peak = 0.0
    max_dd = 0.0
    for t in all_sorted:
        running += t["exit_r"]
        peak = max(peak, running)
        max_dd = max(max_dd, peak - running)

    print("\n" + "-" * 60)
    print(f"TOTAL TRADES      : {total_trades}")
    print(f"OVERALL WIN RATE  : {(total_wins / total_trades * 100) if total_trades else 0:.1f}%")
    print(f"TOTAL R           : {total_r:+.2f}R")
    print(f"AVG R / TRADE     : {(total_r / total_trades) if total_trades else 0:+.2f}R")
    print(f"MAX DRAWDOWN      : {max_dd:.2f}R")
    print("=" * 60)
    print("\nR = multiple of initial risk (SL distance). TP2 win = +2R, straight SL = -1R,")
    print("breakeven = 0R (TP1 hit -> SL moved to entry -> stopped before TP2).")
    print("Sample is limited to ~60 days: Yahoo Finance's max retention for 2m/15m intraday bars.")


CONFIGS = {
    "STRICT (previous defaults)": {"OB_IMPULSE_MULT": 2.0, "FVG_ATR_LIMIT_MULT": 1.3, "RANGING_ATR_MULT": 0.6},
    "LOOSE (new defaults)":       {"OB_IMPULSE_MULT": 1.5, "FVG_ATR_LIMIT_MULT": 1.6, "RANGING_ATR_MULT": 0.5},
}

if __name__ == "__main__":
    import sys
    from core.smc_engine import SMCEngine

    compare = "--compare" in sys.argv

    # Cache historical data once; both configs reuse it (only the thresholds change).
    history = {}
    for cfg in ASSETS:
        print(f"Fetching history for {cfg['name']}...")
        history[cfg["name"]] = {
            "15m": fetch_history(cfg["yf"], "15m", "60d"),
            "3m": fetch_history(cfg["yf"], "2m", "60d"),
        }
        time_module.sleep(2.0)

    def run_with_params(params: dict) -> list:
        SMCEngine.OB_IMPULSE_MULT = params["OB_IMPULSE_MULT"]
        SMCEngine.FVG_ATR_LIMIT_MULT = params["FVG_ATR_LIMIT_MULT"]
        SMCEngine.RANGING_ATR_MULT = params["RANGING_ATR_MULT"]
        trades = []
        for cfg in ASSETS:
            name = cfg["name"]
            df_15m, df_3m = history[name]["15m"], history[name]["3m"]
            if df_15m.empty or df_3m.empty or len(df_3m) < WINDOW + 10:
                continue
            asset_trades = simulate_from_dfs(name, df_15m, df_3m)
            print(f"  [{name}] -> {len(asset_trades)} trades")
            trades.extend(asset_trades)
        return trades

    if compare:
        for label, params in CONFIGS.items():
            print(f"\n\n########## {label}: OB={params['OB_IMPULSE_MULT']}x FVG={params['FVG_ATR_LIMIT_MULT']}x RANGE={params['RANGING_ATR_MULT']}x ##########")
            trades = run_with_params(params)
            report(trades)
    else:
        trades = run_with_params(CONFIGS["LOOSE (new defaults)"])
        report(trades)
