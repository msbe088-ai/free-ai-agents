"""Trade-plan agent (خطة الصفقة): a MECHANICAL, GENERIC entry/exit plan per symbol x timeframe.
Not a recommendation and not the user's own method. Closed candles only; every level is built
from data available at the plan bar (pivots need K bars on the right to be confirmed).

Rule (same for the live plan and the historical check):
  Direction  : the scanner rule (close beyond previous 20-bar high/low + SMA50 side). If no signal in
               the last 20 closed bars, a PENDING plan follows the technical trend (up -> buy setup,
               down -> sell setup, sideways -> no trade).
  Entry      : signal plan -> next bar open after the signal bar (reference = signal close).
               pending plan -> a close beyond the 20-bar high (buy) / low (sell) on the right SMA50 side.
  Stop       : beyond the nearest confirmed opposing swing (low for buy, high for sell) with a
               0.5 x ATR14 buffer; distance kept between 1 and 3 x ATR14.
  Targets    : TP1 = first confirmed swing level in the trade direction (>= 0.25 ATR past entry);
               TP2/TP3 = next swing levels (>= 0.5 ATR apart), then generic Fibonacci extensions
               1.272 / 1.618 / 2.0 / 2.618 of the last 120-bar range.
  History    : win = TP1 touched before the stop; loss = stop touched first (same bar = loss).
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import talib

from .backtest_agent import signal_series
from .common import price_round, r2
from .technical_agent import pivots

K = 5
LOOK = 250
RECENT = 20
BUF, MIN_STOP, MAX_STOP = 0.5, 1.0, 3.0
EXT = [1.272, 1.618, 2.0, 2.618]
METHOD = ("خطة آلية عامة (اختراق 20 شمعة + متوسط 50، وقف خلف أقرب قاع/قمة مؤكدة مع 0.5×ATR، "
          "أهداف من القمم/القيعان السابقة ثم امتدادات فيبوناتشي عامة) — ليست توصية وليست طريقتك الخاصة")


class Ctx:
    def __init__(self, df: pd.DataFrame):
        self.df = df
        self.o, self.h, self.l, self.c = (df[x].values.astype(float) for x in ("open", "high", "low", "close"))
        self.atr = talib.ATR(self.h, self.l, self.c, 14)
        self.sig = signal_series(df).values
        self.sma50 = df["close"].rolling(50).mean().values
        self.hh = df["high"].rolling(20).max().values
        self.ll = df["low"].rolling(20).min().values
        ph, pl = pivots(df, K)
        self.ph, self.pl = np.array(ph, dtype=int), np.array(pl, dtype=int)


def build(cx: Ctx, i: int, side: int, entry: float) -> dict | None:
    """Plan levels from data up to bar i only (pivot j is confirmed when j + K <= i)."""
    a = cx.atr[i]
    if not np.isfinite(a) or a <= 0:
        return None
    ok_h = cx.ph[(cx.ph >= i - LOOK) & (cx.ph <= i - K)]
    ok_l = cx.pl[(cx.pl >= i - LOOK) & (cx.pl <= i - K)]
    w0 = max(0, i - 119)
    hi, lo = cx.h[w0:i + 1].max(), cx.l[w0:i + 1].min()
    rng = hi - lo
    if side > 0:
        opp = [cx.l[j] for j in ok_l if cx.l[j] < entry]
        stop = (max(opp) - BUF * a) if opp else entry - 2 * a
        stop_src = "تحت أقرب قاع مؤكد − 0.5×ATR" if opp else "2×ATR (لا يوجد قاع مؤكد قريب)"
        stop = min(stop, entry - MIN_STOP * a)
        stop = max(stop, entry - MAX_STOP * a)
        lv = sorted({cx.h[j] for j in ok_h if cx.h[j] > entry + 0.25 * a})
        ext = [(hi + (r - 1) * rng, f"امتداد فيبو {r}") for r in EXT]
        better = lambda x, y: x > y
    else:
        opp = [cx.h[j] for j in ok_h if cx.h[j] > entry]
        stop = (min(opp) + BUF * a) if opp else entry + 2 * a
        stop_src = "فوق أقرب قمة مؤكدة + 0.5×ATR" if opp else "2×ATR (لا توجد قمة مؤكدة قريبة)"
        stop = max(stop, entry + MIN_STOP * a)
        stop = min(stop, entry + MAX_STOP * a)
        lv = sorted({cx.l[j] for j in ok_l if cx.l[j] < entry - 0.25 * a}, reverse=True)
        ext = [(lo - (r - 1) * rng, f"امتداد فيبو {r}") for r in EXT]
        better = lambda x, y: x < y
    tg: list[tuple[float, str]] = []
    for x in lv:
        if not tg or abs(x - tg[-1][0]) >= 0.5 * a:
            tg.append((x, "قمة سابقة مؤكدة" if side > 0 else "قاع سابق مؤكد"))
    for x, name in ext:
        ref = tg[-1][0] if tg else entry + side * 0.25 * a
        if better(x, ref) and abs(x - ref) >= 0.5 * a:
            tg.append((x, name))
    tg = tg[:3]
    if not tg:
        return None
    risk = abs(entry - stop)
    return {"side": side, "entry": entry, "stop": stop, "stop_src": stop_src, "atr": a,
            "targets": [{"name": f"TP{k + 1}", "price": p, "src": s, "r": abs(p - entry) / risk}
                        for k, (p, s) in enumerate(tg)]}


def _walk(cx: Ctx, plan: dict, start: int, end: int) -> tuple[str, int, float | None]:
    """From bar `start` (fill at its open) to `end` inclusive. Returns (outcome, bar, fill).
    outcome: 'stop' | 'tp1' | 'open'. Same-bar stop and TP1 counts as stop (conservative)."""
    side, stop, tp1 = plan["side"], plan["stop"], plan["targets"][0]["price"]
    fill = cx.o[start]
    if (side > 0 and fill <= stop) or (side < 0 and fill >= stop):
        return "stop", start, fill
    if (side > 0 and fill >= tp1) or (side < 0 and fill <= tp1):
        return "tp1", start, fill
    for b in range(start, end + 1):
        hs = cx.l[b] <= stop if side > 0 else cx.h[b] >= stop
        ht = cx.h[b] >= tp1 if side > 0 else cx.l[b] <= tp1
        if hs:
            return "stop", b, fill
        if ht:
            return "tp1", b, fill
    return "open", end, fill


def history(cx: Ctx) -> dict:
    n = len(cx.c)
    trades = wins = losses = 0
    i = 60
    while i < n - 1:
        s = int(cx.sig[i])
        if s:
            plan = build(cx, i, s, cx.c[i])
            if plan:
                out, b, _ = _walk(cx, plan, i + 1, n - 1)
                if out == "open":
                    break
                trades += 1
                wins += out == "tp1"
                losses += out == "stop"
                i = b + 1
                continue
        i += 1
    return {"trades": trades, "wins": int(wins), "losses": int(losses)}


def _fmt_plan(plan: dict) -> dict:
    """Rounded levels; R multiples computed from the SAME rounded numbers shown on the page."""
    e, s = price_round(plan["entry"]), price_round(plan["stop"])
    risk = abs(e - s)
    return {"entry": e, "stop": s, "stop_rule": plan["stop_src"], "risk_per_unit": price_round(risk),
            "targets": [{"name": t["name"], "price": price_round(t["price"]),
                         "r": r2(abs(price_round(t["price"]) - e) / risk, 2), "source": t["src"]}
                        for t in plan["targets"]]}


def analyse(df: pd.DataFrame, tkey, trend: str) -> dict:
    """df = closed bars only."""
    if len(df) < 80:
        raise RuntimeError(f"not enough bars ({len(df)})")
    cx = Ctx(df)
    n = len(df)
    last = n - 1
    hist = history(cx)
    def lab(ts):
        k = tkey(ts)
        return k if isinstance(k, str) else pd.Timestamp(k, unit="s").strftime("%Y-%m-%d %H:%M") + " (الرياض)"
    hist.update({"period_from": lab(df.index[60]), "period_to": lab(df.index[-1]),
                 "rule": "رابحة = لمس الهدف الأول قبل الوقف، خاسرة = لمس الوقف أولاً (نفس الشمعة تُحسب خاسرة)"})
    out = {"method": METHOD, "history": hist, "plan_bar": tkey(df.index[last]),
           "atr14": price_round(cx.atr[last]), "sma50": price_round(cx.sma50[last])}
    recent = [j for j in range(max(60, n - RECENT), n) if cx.sig[j] != 0]
    if recent:
        s = recent[-1]
        side = int(cx.sig[s])
        plan = build(cx, s, side, cx.c[s])
        if plan:
            sig_out = {}
            sig_out.update(_fmt_plan(plan))
            sig_out.update({"side": "buy" if side > 0 else "sell", "basis": "signal",
                        "signal_bar": tkey(df.index[s]), "bars_since_signal": last - s})
            sig_out["entry_rule"] = (f"إشارة {'شراء' if side > 0 else 'بيع'} على شمعة {tkey(df.index[s])}: "
                                 f"الدخول عند افتتاح الشمعة التالية (المرجع إغلاق الإشارة {price_round(cx.c[s])})")
            if s == last:
                sig_out["state"], sig_out["status_ar"] = "waiting", "بانتظار الدخول عند افتتاح الشمعة القادمة"
            else:
                st_out, b, fill = _walk(cx, plan, s + 1, last)
                sig_out["fill"] = price_round(fill)
                reached = 0
                stopped = False
                stop_p = plan["stop"]
                for k in range(s + 1, last + 1):  # targets reached in order until the stop
                    lo_, hi_ = cx.l[k], cx.h[k]
                    if (side > 0 and lo_ <= stop_p) or (side < 0 and hi_ >= stop_p):
                        stopped = True
                        break
                    for t_i, t in enumerate(plan["targets"]):
                        if (side > 0 and hi_ >= t["price"]) or (side < 0 and lo_ <= t["price"]):
                            reached = max(reached, t_i + 1)
                if st_out == "stop" and reached == 0:
                    sig_out["state"], sig_out["status_ar"] = "stopped", "ضرب الوقف قبل الهدف الأول (خاسرة)"
                elif reached:
                    sig_out["state"] = f"tp{reached}"
                    sig_out["status_ar"] = f"تحقق الهدف {['الأول', 'الثاني', 'الثالث'][reached - 1]}" + \
                        (" ثم ضرب الوقف الأصلي" if stopped else "")
                else:
                    sig_out["state"], sig_out["status_ar"] = "active", "نشطة: دخلت ولم تصل للهدف الأول ولا الوقف بعد"
            sp = "تحت" if side > 0 else "فوق"
            sig_out["invalidation"] = (f"الخطة تنتهي بخسارة إذا لمس السعر الوقف {price_round(plan['stop'])}؛ "
                                       f"وإذا أغلقت شمعة الدخول {sp} متوسط 50 فالإشارة لم تعد متوافقة مع شرطها")
            if sig_out["state"] == "stopped" or "ثم ضرب" in sig_out["status_ar"]:
                # finished plan: keep a note, then build the next (pending) plan from the trend
                out["previous_plan"] = {"signal_bar": sig_out["signal_bar"], "side": sig_out["side"],
                                        "status_ar": sig_out["status_ar"], "entry": sig_out["entry"],
                                        "stop": sig_out["stop"]}
            else:
                out.update(sig_out)
                return out
    up, down = trend.startswith("صاعد"), trend.startswith("هابط")
    if not (up or down):
        out.update({"side": "none", "basis": "trend", "state": "none",
                    "status_ar": "لا صفقة: الاتجاه عرضي/مختلط ولا توجد خطة قائمة من إشارة حديثة",
                    "buy_trigger": price_round(cx.hh[last]), "sell_trigger": price_round(cx.ll[last]),
                    "entry_rule": f"شرط شراء: إغلاق فوق {price_round(cx.hh[last])} وفوق متوسط 50 | "
                                  f"شرط بيع: إغلاق تحت {price_round(cx.ll[last])} وتحت متوسط 50",
                    "invalidation": "لا توجد خطة قائمة", "targets": []})
        return out
    side = 1 if up else -1
    entry = cx.hh[last] if up else cx.ll[last]
    plan = build(cx, last, side, entry)
    if not plan:
        out.update({"side": "none", "basis": "trend", "state": "none", "targets": [],
                    "status_ar": "لا صفقة: لا توجد مستويات كافية لبناء الخطة", "invalidation": "—"})
        return out
    out.update(_fmt_plan(plan))
    out.update({"side": "buy" if up else "sell", "basis": "trend", "state": "waiting",
                "status_ar": "بانتظار الدخول (لم يتحقق شرط الاختراق بعد)",
                "entry_rule": (f"دخول {'شراء' if up else 'بيع'} عند إغلاق شمعة {'فوق' if up else 'تحت'} "
                               f"{price_round(entry)} (أعلى/أدنى 20 شمعة) و{'فوق' if up else 'تحت'} متوسط 50 "
                               f"({price_round(cx.sma50[last])})")})
    out["invalidation"] = (f"تُلغى إذا تغيّر الاتجاه من {'صاعد' if up else 'هابط'} قبل الاختراق، "
                           f"أو لمس السعر الوقف {price_round(plan['stop'])} بعد الدخول")
    return out
