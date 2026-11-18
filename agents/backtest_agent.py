"""Backtest agent (backtesting.py): ONE simple predefined strategy per symbol, daily bars.

Strategy (fixed, not optimised):
  BUY  when the closed bar closes above the previous 20-bar high AND above SMA50.
  SELL when the closed bar closes below the previous 20-bar low  AND below SMA50.
  Entry at next bar open. Stop = 1.5 x ATR14 from signal close. TP1 = 1.5 x ATR14 (1:1).
Reported: trades, wins (TP1 hit before stop), losses (stop hit first). Nothing else.
If a single bar touches both, backtesting.py's intrabar order is used (no tick data).
"""
from __future__ import annotations

import warnings

import pandas as pd
import talib
from backtesting import Backtest, Strategy

N_BREAK = 20
ATR_MULT = 1.5
RULE_AR = ("شراء: إغلاق فوق أعلى قمة لآخر 20 شمعة وفوق متوسط 50 | بيع: إغلاق تحت أدنى قاع لآخر 20 "
           "شمعة وتحت متوسط 50 | الدخول افتتاح الشمعة التالية | الوقف 1.5×ATR | الهدف الأول 1.5×ATR")


def signal_series(df: pd.DataFrame) -> pd.Series:
    """+1 buy, -1 sell, 0 none — evaluated on each CLOSED bar."""
    c = df["close"]
    hh = df["high"].rolling(N_BREAK).max().shift(1)
    ll = df["low"].rolling(N_BREAK).min().shift(1)
    sma = c.rolling(50).mean()
    sig = pd.Series(0, index=df.index)
    sig[(c > hh) & (c > sma)] = 1
    sig[(c < ll) & (c < sma)] = -1
    return sig


class BreakoutTP1(Strategy):
    def init(self):
        d = self.data.df.rename(columns=str.lower)
        self.sig = self.I(lambda: signal_series(d).values, name="sig", plot=False)
        self.atr = self.I(talib.ATR, self.data.High, self.data.Low, self.data.Close, 14,
                          name="atr", plot=False)

    def next(self):
        if self.position or self.orders:
            return
        s, a, c = self.sig[-1], self.atr[-1], self.data.Close[-1]
        if not a or a != a:
            return
        if s == 1:
            self.buy(size=1, sl=c - ATR_MULT * a, tp=c + ATR_MULT * a)
        elif s == -1:
            self.sell(size=1, sl=c + ATR_MULT * a, tp=c - ATR_MULT * a)


def run(df: pd.DataFrame) -> dict:
    d = df.rename(columns=str.title)[["Open", "High", "Low", "Close", "Volume"]].copy()
    d.index = d.index.tz_localize(None)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        bt = Backtest(d, BreakoutTP1, cash=1e12, commission=0.0, exclusive_orders=False,
                      trade_on_close=False, finalize_trades=False)
        stats = bt.run()
    tr = stats["_trades"]
    wins = int((tr["PnL"] > 0).sum()) if len(tr) else 0
    losses = int((tr["PnL"] <= 0).sum()) if len(tr) else 0
    return {"status": "ok", "trades": int(len(tr)), "wins": wins, "losses": losses,
            "period_from": str(d.index[0].date()), "period_to": str(d.index[-1].date()),
            "timeframe": "يومي", "rule": RULE_AR, "library": "backtesting.py",
            "note": "صفقة مفتوحة في آخر البيانات لا تُحسب. اختبار تاريخي فقط وليس توقعاً."}
