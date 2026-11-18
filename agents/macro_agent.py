"""Macro agent: FRED public CSV (no API key)."""
from __future__ import annotations

import io
from datetime import datetime, timezone

import pandas as pd

from .common import http_get, ok, fail, r2

SOURCE = "FRED (St. Louis Fed) CSV"
SERIES = {
    "FEDFUNDS": ("سعر الفائدة الفيدرالية الفعلي", "%", "شهري"),
    "DGS10": ("عائد سندات الخزانة 10 سنوات", "%", "يومي"),
    "DGS2": ("عائد سندات الخزانة سنتين", "%", "يومي"),
    "CPIAUCSL": ("التضخم السنوي (CPI)", "%", "شهري"),
    "UNRATE": ("معدل البطالة", "%", "شهري"),
}


def _series(sid: str) -> pd.Series:
    r = http_get("https://fred.stlouisfed.org/graph/fredgraph.csv", params={"id": sid})
    df = pd.read_csv(io.StringIO(r.text))
    df.columns = ["date", "value"]
    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    df = df.dropna()
    return pd.Series(df["value"].values, index=pd.to_datetime(df["date"]))


def fetch() -> dict:
    items = []
    errors = []
    for sid, (ar, unit, freq) in SERIES.items():
        try:
            s = _series(sid)
            if sid == "CPIAUCSL":  # year-over-year % computed from the index
                s = (s / s.shift(12) - 1) * 100
                s = s.dropna()
            items.append({"id": sid, "name": ar, "unit": unit, "freq": freq,
                          "value": r2(s.iloc[-1]), "date": s.index[-1].strftime("%Y-%m-%d"),
                          "prev": r2(s.iloc[-2]), "prev_date": s.index[-2].strftime("%Y-%m-%d")})
        except Exception as e:  # noqa: BLE001
            errors.append(f"{sid}: {e}")
    if not items:
        return fail(SOURCE, "; ".join(errors))
    spread = None
    d = {x["id"]: x for x in items}
    if "DGS10" in d and "DGS2" in d and d["DGS10"]["date"] == d["DGS2"]["date"]:
        spread = r2(d["DGS10"]["value"] - d["DGS2"]["value"])
    last = max(datetime.strptime(x["date"], "%Y-%m-%d") for x in items).replace(tzinfo=timezone.utc)
    return ok({"items": items, "spread_10y_2y": spread, "errors": errors,
               "note": "بيانات رسمية بتأخير طبيعي (الشهرية تصدر بعد نهاية الشهر)"}, SOURCE, last)
