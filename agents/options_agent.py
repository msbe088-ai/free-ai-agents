"""Options agent: delayed Yahoo option-chain summary for the nearest expiry."""
from __future__ import annotations

import math

import yfinance as yf

from .common import ok, fail, r2, retry_call, now_utc

SOURCE = "Yahoo Finance option chain (متأخر وقد يكون ناقصاً)"


def fetch(symbol: str, spot: float) -> dict:
    try:
        t = yf.Ticker(symbol)
        exps = retry_call(lambda: t.options, retries=3, base_sleep=3)
        if not exps:
            raise RuntimeError("no expiries")
        today = now_utc().date().isoformat()
        exps = [e for e in exps if e >= today] or list(exps)
        exp = exps[0]
        ch = retry_call(lambda: t.option_chain(exp), retries=3, base_sleep=3)
        calls, puts = ch.calls.fillna(0), ch.puts.fillna(0)
        cv, pv = float(calls["volume"].sum()), float(puts["volume"].sum())
        co, po = float(calls["openInterest"].sum()), float(puts["openInterest"].sum())

        def top(df, n=3):
            d = df.sort_values("openInterest", ascending=False).head(n)
            return [{"strike": r2(s), "oi": int(o)} for s, o in zip(d["strike"], d["openInterest"])]

        def atm_iv(df):
            if df.empty:
                return None
            i = (df["strike"] - spot).abs().idxmin()
            v = float(df.loc[i, "impliedVolatility"])
            return r2(v * 100, 1) if math.isfinite(v) and v > 0 else None
        return ok({"expiry": exp, "expiries_available": len(exps), "spot_used": r2(spot),
                   "calls_volume": int(cv), "puts_volume": int(pv),
                   "calls_oi": int(co), "puts_oi": int(po),
                   "pc_ratio_volume": r2(pv / cv) if cv else None,
                   "pc_ratio_oi": r2(po / co) if co else None,
                   "top_call_oi": top(calls), "top_put_oi": top(puts),
                   "atm_iv_call_pct": atm_iv(calls), "atm_iv_put_pct": atm_iv(puts)},
                  SOURCE, now_utc())
    except Exception as e:  # noqa: BLE001
        return fail(SOURCE, e)
