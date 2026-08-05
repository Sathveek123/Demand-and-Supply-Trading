# Telegram Signal & Reporting Format — SMC Trading Bot v2.1

## 1. Trade Signal Payload Format

```text
🟢 BUY SIGNAL — BTC/USDT

Entry Zone : 64350.0 – 64410.0
Entry Price: 64380.0
Stop Loss  : 64150.0 (Risk: 230 pts)
Target TP1 : 64610.0 (1:1 RR)
Target TP2 : 64840.0 (1:2 RR)

Setup      : Bullish Order Block + FVG Confluence
Timeframe  : 15M Trend (BULLISH) / 3M Entry
Confidence : 92% 🔥
Hold Time  : 15–45 Mins

⚡ Rule Checklist:
  • 15M Trend Aligned : YES ✅
  • Unmitigated OB   : YES ✅
  • FVG Confluence   : YES ✅
  • 3M Confirmation  : Engulfing ✅

Status: Signal Active 🚀
```

---

## 2. Performance Report Format

```text
📊 Daily Performance Report (9 PM IST) — 05-08-2026

🏆 Performance Summary:
Total Trades : 5
Wins         : 4 ✅
Losses       : 1 ❌
Win Rate     : 80% 🔥
Net Result   : +1,240.5 pts

Asset Breakdown:
• BTC/USDT : 2/2 Wins (100%)
• ETH/USDT : 1/1 Wins (100%)
• XAUUSD   : 1/1 Wins (100%)
• EURUSD   : 0/1 Wins (0%)

Recent Closed Trades:
  BTC/USDT BUY → TP2 ✅ +460 pts
  ETH/USDT BUY → TP2 ✅ +35 pts
  XAUUSD BUY → TP2 ✅ +12.5 pts
  EURUSD BUY → SL ❌ -0.0012 pts
```
