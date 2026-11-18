"""Crypto agent: klines from Binance's public market-data mirror data-api.binance.vision
(keyless, works where api.binance.com may return HTTP 451)."""
from __future__ import annotations

import pandas as pd

from .common import http_get, now_utc

SOURCE = "Binance data-api.binance.vision (مجاني)"
BASE = "https://data-api.binance.vision/api/v3/klines"


def _klines(symbol: str, interval: str, limit: int = 1000) -> tuple[pd.DataFrame, bool]:
    r = http_get(BASE, params={"symbol": symbol, "interval": interval, "limit": limit})
    rows = r.json()
    if not rows:
        raise RuntimeError(f"no klines for {symbol} {interval}")
    df = pd.DataFrame(rows, columns=["t", "open", "high", "low", "close", "volume", "ct",
                                     "qv", "n", "tb", "tq", "ig"])
    df["time"] = pd.to_datetime(df["t"], unit="ms", utc=True)
    for c in ["open", "high", "low", "close", "volume"]:
        df[c] = df[c].astype(float)
    forming = bool(int(df["ct"].iloc[-1]) > int(now_utc().timestamp() * 1000))
    return df.set_index("time")[["open", "high", "low", "close", "volume"]], forming


def fetch(symbol: str) -> dict:
    out = {"forming": {}, "source": SOURCE}
    for tf, iv in (("1d", "1d"), ("1h", "1h"), ("4h", "4h")):
        df, forming = _klines(symbol, iv)
        out[tf] = df
        out["forming"][tf] = forming
    return out


def ticker_24h(symbols: list[str]) -> dict:
    """24h stats for the crypto watchlist (one request)."""
    import json
    r = http_get("https://data-api.binance.vision/api/v3/ticker/24hr",
                 params={"symbols": json.dumps(symbols, separators=(",", ":"))})
    return {d["symbol"]: {"last": float(d["lastPrice"]),
                          "change_pct_24h": float(d["priceChangePercent"]),
                          "high_24h": float(d["highPrice"]), "low_24h": float(d["lowPrice"]),
                          "quote_volume_24h": float(d["quoteVolume"])} for d in r.json()}
