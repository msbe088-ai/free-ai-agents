"""Recompute RSI14 / SMA50 from the page's own closed daily bars with plain pandas (no TA-Lib)
and compare with the technical agent's numbers."""
import json, urllib.request
import pandas as pd
BASE = "https://msbe088-ai.github.io/free-ai-agents/data/"
idx = json.load(urllib.request.urlopen(BASE + "index.json"))
bad = 0
for s in idx["symbols"]:
    d = json.load(urllib.request.urlopen(BASE + f"sym/{s['symbol']}.json"))
    t = d["tf"]["1d"]; bars = t["bars"][:-1] if t["last_bar_forming"] else t["bars"]
    c = pd.Series([b[4] for b in bars])
    delta = c.diff(); up = delta.clip(lower=0); dn = -delta.clip(upper=0)
    au = up.ewm(alpha=1/14, adjust=False).mean(); ad = dn.ewm(alpha=1/14, adjust=False).mean()
    rsi = float((100 - 100 / (1 + au / ad)).iloc[-1]); sma50 = float(c.rolling(50).mean().iloc[-1])
    ta = t["technical"]
    ok = abs(rsi - ta["rsi14"]) <= 0.3 and abs(sma50 - ta["sma50"]) / sma50 <= 0.001 and ta["close"] == c.iloc[-1]
    bad += not ok
    print(("OK " if ok else "MISMATCH "), s["symbol"], "RSI page", ta["rsi14"], "indep", round(rsi, 1), "| SMA50 page", ta["sma50"], "indep", round(sma50, 2))
print("mismatches", bad)
