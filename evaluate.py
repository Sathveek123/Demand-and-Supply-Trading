"""
Rigorous out-of-sample evaluation of the SMC Pullback strategy.

Unlike backtest.py's --compare (which tests configs on the SAME data it
measures them on — in-sample, prone to overfitting), this script:

  1. Splits each asset's ~60-day history chronologically into a TRAIN
     window (first 70%) and a TEST window (last 30%) that the selection
     step never sees.
  2. Runs a small experiment matrix (confidence filter strictness x
     asset inclusion) on TRAIN only, picks the best variant by
     expectancy per trade.
  3. Reports that variant's performance on TEST — numbers the selection
     process never touched. This is the honest, out-of-sample score.
  4. Runs a Monte Carlo trade-order shuffle (2000 sims) on the TEST
     trades to show the realistic range of drawdown you could hit, not
     just the one path that happened to occur.
  5. Converts the out-of-sample metrics into a transparent 0-10 rating
     using a documented formula (see `rate()`) — not a guess.

Known ceiling: Yahoo Finance retains ~60 days of 2m/15m intraday data,
so TRAIN+TEST together still only cover ~60 days. A 70/30 split of that
is a thin test set (order of 10-15 days) — treat the resulting rating as
a lower-confidence estimate, not a long-run guarantee.

Run: python evaluate.py
"""
import random
import pandas as pd
from backtest import ASSETS, fetch_history, WINDOW
from core.smc_engine import SMCEngine


def simulate_window(name: str, df_15m: pd.DataFrame, df_3m: pd.DataFrame, min_confidence: str = "MODERATE") -> list:
    """Same walk-forward replay as backtest.simulate_from_dfs, with a confidence-floor knob."""
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
                open_trade["sl"] = open_trade["entry"]
            elif result == "TP2_HIT":
                open_trade["exit_r"] = 2.0
                trades.append(open_trade)
                open_trade = None
            elif result == "SL_HIT":
                open_trade["exit_r"] = 0.0 if open_trade["tp1_hit"] else -1.0
                trades.append(open_trade)
                open_trade = None

        if open_trade is not None:
            continue

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

        conf = analysis.get("confidence", "")
        if min_confidence == "HIGH" and "HIGH" not in conf:
            continue
        if min_confidence == "MODERATE" and "LOW" in conf:
            continue

        open_trade = {
            "asset": name, "direction": analysis["signal_type"], "entry": analysis["entry"],
            "sl": analysis["stop_loss"], "tp1": analysis["tp1"], "tp2": analysis["tp2"],
            "confidence": conf, "tp1_hit": False, "open_ts": current_ts,
        }

    return trades


def split_train_test(df: pd.DataFrame, train_frac: float = 0.7) -> tuple:
    cut = int(len(df) * train_frac)
    return df.iloc[:cut].reset_index(drop=True), df.iloc[cut:].reset_index(drop=True)


def metrics(trades: list) -> dict:
    if not trades:
        return {"trades": 0, "win_rate": 0.0, "total_r": 0.0, "expectancy": 0.0, "profit_factor": 0.0, "max_dd": 0.0}
    rs = [t["exit_r"] for t in trades]
    wins = [r for r in rs if r > 0]
    losses = [r for r in rs if r < 0]
    gross_win = sum(wins)
    gross_loss = abs(sum(losses))
    profit_factor = (gross_win / gross_loss) if gross_loss > 0 else (float("inf") if gross_win > 0 else 0.0)

    running, peak, max_dd = 0.0, 0.0, 0.0
    for r in rs:
        running += r
        peak = max(peak, running)
        max_dd = max(max_dd, peak - running)

    return {
        "trades": len(rs),
        "win_rate": (len(wins) / len(rs)) * 100,
        "total_r": sum(rs),
        "expectancy": sum(rs) / len(rs),
        "profit_factor": profit_factor,
        "max_dd": max_dd,
    }


def monte_carlo_drawdown(trades: list, n_sims: int = 2000) -> dict:
    if not trades:
        return {"median_dd": 0.0, "p95_dd": 0.0}
    rs = [t["exit_r"] for t in trades]
    dds = []
    rng = random.Random(42)
    for _ in range(n_sims):
        shuffled = rs[:]
        rng.shuffle(shuffled)
        running, peak, max_dd = 0.0, 0.0, 0.0
        for r in shuffled:
            running += r
            peak = max(peak, running)
            max_dd = max(max_dd, peak - running)
        dds.append(max_dd)
    dds.sort()
    return {
        "median_dd": dds[len(dds) // 2],
        "p95_dd": dds[int(len(dds) * 0.95)],
    }


def rate(m: dict) -> float:
    """
    Transparent 0-10 rating from out-of-sample metrics (no subjective fudge factor):
      40% expectancy   -- avg R/trade vs a 0.5R "excellent" benchmark for this 1:2 setup
      30% profit factor-- vs a 2.0 "excellent" benchmark
      20% drawdown     -- penalizes max_dd above 5R
      10% sample size  -- <20 out-of-sample trades caps confidence, regardless of result
    """
    if m["trades"] == 0:
        return 0.0
    expectancy_score = max(0.0, min(1.0, m["expectancy"] / 0.5))
    pf_capped = min(m["profit_factor"], 2.0) if m["profit_factor"] != float("inf") else 2.0
    pf_score = pf_capped / 2.0
    dd_score = max(0.0, 1.0 - (m["max_dd"] / 5.0))
    sample_score = min(1.0, m["trades"] / 20.0)

    raw = 0.4 * expectancy_score + 0.3 * pf_score + 0.2 * dd_score + 0.1 * sample_score
    return round(raw * 10, 1)


VARIANTS = {
    "A: MODERATE+ conf, all 4 assets":        {"min_confidence": "MODERATE", "assets": ["BTC/USDT", "ETH/USDT", "XAUUSD", "EURUSD"]},
    "B: HIGH-only conf, all 4 assets":        {"min_confidence": "HIGH",     "assets": ["BTC/USDT", "ETH/USDT", "XAUUSD", "EURUSD"]},
    "C: MODERATE+ conf, drop XAUUSD":         {"min_confidence": "MODERATE", "assets": ["BTC/USDT", "ETH/USDT", "EURUSD"]},
    "D: HIGH-only conf, drop XAUUSD":         {"min_confidence": "HIGH",     "assets": ["BTC/USDT", "ETH/USDT", "EURUSD"]},
}


def run_variant(data: dict, variant: dict) -> list:
    trades = []
    for name in variant["assets"]:
        df_15m, df_3m = data[name]["15m"], data[name]["3m"]
        if df_15m.empty or df_3m.empty or len(df_3m) < WINDOW + 10:
            continue
        trades.extend(simulate_window(name, df_15m, df_3m, min_confidence=variant["min_confidence"]))
    return trades


if __name__ == "__main__":
    print("Fetching ~60 days of history per asset...")
    full_history = {}
    for cfg in ASSETS:
        df_15m = fetch_history(cfg["yf"], "15m", "60d")
        df_3m = fetch_history(cfg["yf"], "2m", "60d")
        full_history[cfg["name"]] = {"15m": df_15m, "3m": df_3m}
        print(f"  {cfg['name']}: 15m={len(df_15m)} rows, 3m={len(df_3m)} rows")

    train_data, test_data = {}, {}
    for name, dfs in full_history.items():
        tr15, te15 = split_train_test(dfs["15m"])
        tr3, te3 = split_train_test(dfs["3m"])
        train_data[name] = {"15m": tr15, "3m": tr3}
        test_data[name] = {"15m": te15, "3m": te3}

    print("\n" + "=" * 70)
    print("STEP 1: Selecting best variant on TRAIN data (first 70%)")
    print("=" * 70)
    train_results = {}
    for label, variant in VARIANTS.items():
        trades = run_variant(train_data, variant)
        m = metrics(trades)
        train_results[label] = (m, variant)
        print(f"\n{label}")
        print(f"  Trades={m['trades']}  WinRate={m['win_rate']:.1f}%  "
              f"Expectancy={m['expectancy']:+.2f}R  ProfitFactor={m['profit_factor']:.2f}  TotalR={m['total_r']:+.2f}")

    best_label = max(train_results, key=lambda k: train_results[k][0]["expectancy"] if train_results[k][0]["trades"] >= 5 else -999)
    best_variant = train_results[best_label][1]
    print(f"\n>>> Best on TRAIN by expectancy: {best_label}")

    print("\n" + "=" * 70)
    print("STEP 2: Validating that variant on TEST data (last 30%, never used to pick it)")
    print("=" * 70)
    test_trades = run_variant(test_data, best_variant)
    test_m = metrics(test_trades)
    print(f"\nOut-of-sample TEST results for '{best_label}':")
    print(f"  Trades          : {test_m['trades']}")
    print(f"  Win rate        : {test_m['win_rate']:.1f}%")
    print(f"  Expectancy      : {test_m['expectancy']:+.2f}R / trade")
    print(f"  Profit factor   : {test_m['profit_factor']:.2f}")
    print(f"  Total R         : {test_m['total_r']:+.2f}R")
    print(f"  Max drawdown    : {test_m['max_dd']:.2f}R (actual path)")

    mc = monte_carlo_drawdown(test_trades)
    print(f"\nMonte Carlo (2000 reshuffles of the same test trades, same win/loss outcomes, different order):")
    print(f"  Median max drawdown : {mc['median_dd']:.2f}R")
    print(f"  95th pct drawdown   : {mc['p95_dd']:.2f}R  (worst-case-ish scenario to plan risk around)")

    score = rate(test_m)
    print("\n" + "=" * 70)
    print(f"OUT-OF-SAMPLE RATING: {score}/10")
    print("=" * 70)
    print("Formula: 40% expectancy (vs 0.5R benchmark) + 30% profit factor (vs 2.0 benchmark)")
    print("       + 20% drawdown control (penalized above 5R) + 10% sample size (caps below 20 trades)")
    if test_m["trades"] < 20:
        print(f"\nNOTE: only {test_m['trades']} out-of-sample trades — too small a sample to trust this")
        print("number as a long-run truth. Treat it as directional, not final, until more live/backtest data exists.")
