"""Data agent: OHLC for US stocks/ETFs from Yahoo Finance (yfinance), 1d / 1h / 4h.

4h is built from Yahoo 1h bars (Yahoo has no native 4h): each New-York session is split
into 09:30-13:30 and 13:30-16:00 bars. Data is free and may be delayed.
"""
from __future__ import annotations

import pandas as pd
import yfinance as yf

from .common import retry_call, now_utc

SOURCE = "Yahoo Finance via yfinance (مجاني، قد يتأخر)"
NY = "America/New_York"


def _clean(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        raise RuntimeError("empty dataframe from Yahoo")
    df = df.rename(columns=str.lower)[["open", "high", "low", "close", "volume"]].copy()
    df = df.dropna(subset=["open", "high", "low", "close"])
    idx = df.index
    if idx.tz is None:
        idx = idx.tz_localize("UTC")
    df.index = idx.tz_convert("UTC")
    df = df[~df.index.duplicated(keep="last")].sort_index()
    if df.empty:
        raise RuntimeError("no valid rows from Yahoo")
    return df


def _history(symbol: str, period: str, interval: str) -> pd.DataFrame:
    def _f():
        d = yf.Ticker(symbol).history(period=period, interval=interval, auto_adjust=True,
                                      actions=False, raise_errors=True)
        return _clean(d)
    return retry_call(_f, retries=4, base_sleep=4)


def to_4h(h1: pd.DataFrame) -> pd.DataFrame:
    ny = h1.copy()
    ny.index = ny.index.tz_convert(NY)
    day = ny.index.normalize()
    minutes = (ny.index - day).total_seconds() / 60 - (9 * 60 + 30)
    block = (minutes // 240).astype(int)
    key = pd.Series(list(zip(day, block)), index=ny.index)
    rows = []
    for (d, b), g in ny.groupby(key.values, sort=True):
        rows.append({"time": g.index[0], "open": g["open"].iloc[0], "high": g["high"].max(),
                     "low": g["low"].min(), "close": g["close"].iloc[-1],
                     "volume": g["volume"].sum(), "n": len(g)})
    out = pd.DataFrame(rows).set_index("time").sort_index()
    out.index = out.index.tz_convert("UTC")
    return out


def _forming_daily(df: pd.DataFrame) -> bool:
    """Last daily bar is still forming if it is today's NY session and before 16:00 NY."""
    now_ny = now_utc().astimezone(pd.Timestamp.now(tz=NY).tz)
    last_day = df.index[-1].tz_convert(NY).date()
    return last_day == now_ny.date() and (now_ny.hour, now_ny.minute) < (16, 0)


def fetch(symbol: str) -> dict:
    """Return {'1d': df, '1h': df, '4h': df, 'forming': {...}} or raise."""
    d1 = _history(symbol, "2y", "1d")
    h1 = _history(symbol, "365d", "1h")
    h4 = to_4h(h1)
    now = pd.Timestamp(now_utc())
    forming = {
        "1d": _forming_daily(d1),
        "1h": bool(h1.index[-1] + pd.Timedelta(hours=1) > now),
        # a 4h stock block ends at 13:30 or 16:00 NY
        "4h": bool(h4.index[-1] + pd.Timedelta(hours=4) > now and
                   (h4["n"].iloc[-1] < 4 and now - h1.index[-1] < pd.Timedelta(hours=1))),
    }
    return {"1d": d1, "1h": h1, "4h": h4.drop(columns=["n"]), "forming": forming,
            "source": SOURCE}
