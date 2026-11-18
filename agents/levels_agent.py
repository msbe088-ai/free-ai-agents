"""Levels / Fibonacci agent: generic retracement of the last major swing (highest high /
lowest low of the lookback window). Generic method, NOT the user's own Fibonacci method."""
from __future__ import annotations

import pandas as pd

from .common import price_round

RATIOS = [0.0, 0.236, 0.382, 0.5, 0.618, 0.786, 1.0]


def analyse(df: pd.DataFrame, tkey, lookback: int = 120) -> dict:
    w = df.iloc[-lookback:]
    ih, il = int(w["high"].values.argmax()), int(w["low"].values.argmin())
    hi, lo = float(w["high"].iloc[ih]), float(w["low"].iloc[il])
    up = il < ih  # low came first -> up swing, retrace downwards from the high
    rng = hi - lo
    levels = []
    for r in RATIOS:
        p = hi - r * rng if up else lo + r * rng
        levels.append({"ratio": r, "price": price_round(p)})
    close = float(df["close"].iloc[-1])
    below = [x for x in levels if x["price"] <= close]
    above = [x for x in levels if x["price"] > close]
    return {
        "swing": "صاعدة" if up else "هابطة",
        "swing_high": {"price": price_round(hi), "time": tkey(w.index[ih])},
        "swing_low": {"price": price_round(lo), "time": tkey(w.index[il])},
        "levels": levels,
        "nearest_below": max(below, key=lambda x: x["price"]) if below else None,
        "nearest_above": min(above, key=lambda x: x["price"]) if above else None,
        "lookback_bars": lookback,
        "method": "تصحيح فيبوناتشي عام لآخر موجة كبرى (أعلى قمة وأدنى قاع في آخر 120 شمعة) — طريقة عامة وليست طريقتك",
    }
