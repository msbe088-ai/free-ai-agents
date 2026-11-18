"""Candle patterns agent (TA-Lib)."""
from __future__ import annotations

import pandas as pd
import talib

PATTERNS = {
    "CDLENGULFING": "ابتلاعية",
    "CDLHAMMER": "مطرقة",
    "CDLINVERTEDHAMMER": "مطرقة مقلوبة",
    "CDLHANGINGMAN": "الرجل المشنوق",
    "CDLSHOOTINGSTAR": "الشهاب",
    "CDLDOJI": "دوجي",
    "CDLMORNINGSTAR": "نجمة الصباح",
    "CDLEVENINGSTAR": "نجمة المساء",
    "CDLHARAMI": "هارامي",
    "CDLPIERCING": "خط الاختراق",
    "CDLDARKCLOUDCOVER": "الغطاء السحابي المظلم",
    "CDL3WHITESOLDIERS": "الجنود الثلاثة البيض",
    "CDL3BLACKCROWS": "الغربان الثلاثة السود",
    "CDLMARUBOZU": "ماروبوزو",
}


def analyse(df: pd.DataFrame, tkey, recent: int = 10, markers: int = 60) -> dict:
    o, h, l, c = (df[x].values for x in ("open", "high", "low", "close"))
    hits = []
    n = len(df)
    for fn, ar in PATTERNS.items():
        res = getattr(talib, fn)(o, h, l, c)
        for i in range(max(0, n - markers), n):
            v = int(res[i])
            if v != 0:
                direction = "neutral" if fn == "CDLDOJI" else ("bull" if v > 0 else "bear")
                hits.append({"time": tkey(df.index[i]), "idx_from_end": n - 1 - i,
                             "code": fn, "name": ar, "direction": direction})
    hits.sort(key=lambda x: x["idx_from_end"])
    last = [x for x in hits if x["idx_from_end"] < recent]
    return {"recent": last, "markers": hits,
            "counts_recent": {"bull": sum(x["direction"] == "bull" for x in last),
                              "bear": sum(x["direction"] == "bear" for x in last),
                              "neutral": sum(x["direction"] == "neutral" for x in last)},
            "window_bars": recent, "library": "TA-Lib"}
