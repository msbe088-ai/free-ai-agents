"""Technical analysis agent: generic pivot swings, trend, support/resistance, RSI, ATR.

Generic textbook method (fractal pivots, moving averages). It is NOT the user's own
SMC / Fibonacci method.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import talib

from .common import price_round, r2

PIVOT_K = 5  # bars on each side


def pivots(df: pd.DataFrame, k: int = PIVOT_K) -> tuple[list[int], list[int]]:
    h, l = df["high"].values, df["low"].values
    highs, lows = [], []
    for i in range(k, len(df) - k):
        if h[i] == h[i - k:i + k + 1].max() and (h[i] > h[i - k:i]).all():
            highs.append(i)
        if l[i] == l[i - k:i + k + 1].min() and (l[i] < l[i - k:i]).all():
            lows.append(i)
    return highs, lows


def _cluster(levels: list[float], tol: float) -> list[float]:
    out: list[list[float]] = []
    for v in sorted(levels):
        if out and abs(v - np.mean(out[-1])) <= tol:
            out[-1].append(v)
        else:
            out.append([v])
    return [float(np.mean(c)) for c in out]


def analyse(df: pd.DataFrame, tkey) -> dict:
    """df = closed bars only. tkey(ts) -> chart time key."""
    if len(df) < 60:
        raise RuntimeError(f"not enough bars ({len(df)})")
    c, h, l = df["close"].values, df["high"].values, df["low"].values
    close = float(c[-1])
    rsi = talib.RSI(c, 14)[-1]
    atr = talib.ATR(h, l, c, 14)[-1]
    sma20 = talib.SMA(c, 20)[-1]
    sma50 = talib.SMA(c, 50)[-1]
    sma200 = talib.SMA(c, 200)[-1] if len(c) >= 200 else np.nan
    hi_idx, lo_idx = pivots(df)
    swings_h = [{"time": tkey(df.index[i]), "price": price_round(h[i])} for i in hi_idx[-6:]]
    swings_l = [{"time": tkey(df.index[i]), "price": price_round(l[i])} for i in lo_idx[-6:]]

    # structure from last two swing highs and lows
    struct = "غير كافٍ"
    if len(hi_idx) >= 2 and len(lo_idx) >= 2:
        hh = h[hi_idx[-1]] > h[hi_idx[-2]]
        hl = l[lo_idx[-1]] > l[lo_idx[-2]]
        struct = ("قمم وقيعان أعلى (صاعد)" if hh and hl else
                  "قمم وقيعان أدنى (هابط)" if (not hh and not hl) else "متذبذب/عرضي")
    ma_trend = "فوق المتوسطين 50 و200" if (np.isfinite(sma200) and close > sma50 > 0 and close > sma200) else \
        "تحت المتوسطين 50 و200" if (np.isfinite(sma200) and close < sma50 and close < sma200) else \
        ("فوق متوسط 50" if close > sma50 else "تحت متوسط 50")
    score = (1 if close > sma50 else -1) + ((1 if close > sma200 else -1) if np.isfinite(sma200) else 0) + \
        (1 if "صاعد" in struct else -1 if "هابط" in struct else 0)
    trend = "صاعد" if score >= 2 else "هابط" if score <= -2 else "عرضي/مختلط"

    tol = 0.5 * atr if np.isfinite(atr) else close * 0.005
    look = 250
    res_raw = [h[i] for i in hi_idx if i >= len(df) - look and h[i] > close]
    sup_raw = [l[i] for i in lo_idx if i >= len(df) - look and l[i] < close]
    resist = sorted(_cluster(res_raw, tol))[:3]
    support = sorted(_cluster(sup_raw, tol), reverse=True)[:3]
    return {
        "close": price_round(close), "bar_time": tkey(df.index[-1]),
        "trend": trend, "structure": struct, "ma_position": ma_trend,
        "rsi14": r2(rsi, 1), "atr14": price_round(atr),
        "sma20": price_round(sma20), "sma50": price_round(sma50), "sma200": price_round(sma200),
        "supports": [price_round(x) for x in support],
        "resistances": [price_round(x) for x in resist],
        "swing_highs": swings_h, "swing_lows": swings_l,
        "method": "نقاط ارتكاز عامة (5 شموع يمين ويسار) + متوسطات متحركة — طريقة عامة وليست طريقتك الخاصة",
    }
