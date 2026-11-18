"""Scanner agent: lists watchlist symbols whose LAST CLOSED bar triggers the backtest rule."""
from __future__ import annotations

import pandas as pd

from .backtest_agent import signal_series


def current_signal(df_closed: pd.DataFrame) -> int:
    if len(df_closed) < 60:
        return 0
    return int(signal_series(df_closed).iloc[-1])


def scan(results: list[dict]) -> dict:
    rows = []
    for r in results:
        for tf in ("1d", "4h"):
            s = r.get("signals", {}).get(tf, 0)
            if s:
                rows.append({"symbol": r["symbol"], "tf": tf, "side": "شراء" if s > 0 else "بيع",
                             "close": r.get("tf_close", {}).get(tf), "bar_time": r.get("tf_bar", {}).get(tf)})
    return {"status": "ok", "signals": rows, "scanned": len(results),
            "rule": "نفس قاعدة وكيل الاختبار التاريخي (اختراق 20 شمعة مع متوسط 50) على آخر شمعة مغلقة، يومي و4 ساعات"}
