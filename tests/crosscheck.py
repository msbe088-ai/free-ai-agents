"""Independent cross-check: compare page JSON bars against a fresh fetch (same bar timestamps).
Stocks: yf.download (different code path from the agent's Ticker.history). Crypto: raw Binance klines via requests."""
import json, sys, urllib.request
import pandas as pd, requests, yfinance as yf

BASE = "https://msbe088-ai.github.io/free-ai-agents/data/"
idx = json.load(urllib.request.urlopen(BASE + "index.json"))
rows = []
for s in idx["symbols"]:
    d = json.load(urllib.request.urlopen(BASE + f"sym/{s['symbol']}.json"))
    page1d = {b[0]: b for b in d["tf"]["1d"]["bars"]}
    page1h = {b[0]: b for b in d["tf"]["1h"]["bars"]}
    if s["kind"] == "stock":
        f = yf.download(d["ticker"], period="1mo", interval="1d", auto_adjust=True, progress=False, multi_level_index=False)
        fresh1d = {ts.strftime("%Y-%m-%d"): float(c) for ts, c in zip(f.index, f["Close"])}
        h = yf.download(d["ticker"], period="5d", interval="1h", auto_adjust=True, progress=False, multi_level_index=False)
        hi = h.index.tz_convert("UTC") if h.index.tz is not None else h.index.tz_localize("UTC")
        fresh1h = {int(ts.timestamp()) + 10800: float(c) for ts, c in zip(hi, h["Close"])}
        src = "yf.download"
    else:
        def kl(iv, key):
            r = requests.get("https://data-api.binance.vision/api/v3/klines", params={"symbol": d["ticker"], "interval": iv, "limit": 60}, timeout=20).json()
            return {key(x[0]): float(x[4]) for x in r}
        fresh1d = kl("1d", lambda t: pd.Timestamp(t, unit="ms", tz="UTC").strftime("%Y-%m-%d"))
        fresh1h = kl("1h", lambda t: t // 1000 + 10800)
        src = "Binance klines"
    for tf, page, fresh in (("1d", page1d, fresh1d), ("1h", page1h, fresh1h)):
        forming = d["tf"][tf]["last_bar_forming"]
        keys = sorted(set(page) & set(fresh))
        if forming and keys and keys[-1] == max(page):
            keys = keys[:-1]  # page's forming bar is expected to differ
        k = keys[-1] if keys else None
        pc = page[k][4] if k else None
        fc = fresh[k] if k else None
        diff = None if k is None else abs(pc - fc) / fc * 100
        rows.append({"symbol": s["symbol"], "tf": tf, "bar": k, "page_close": pc, "fresh_close": round(fc, 6) if fc else None,
                     "diff_pct": None if diff is None else round(diff, 4), "ok": diff is not None and diff <= 0.05, "fresh_src": src})
json.dump(rows, open(sys.argv[1], "w"), ensure_ascii=False, indent=1)
for r in rows:
    print(("OK " if r["ok"] else "MISMATCH ") + json.dumps(r, ensure_ascii=False))
print("ok", sum(r["ok"] for r in rows), "/", len(rows))
