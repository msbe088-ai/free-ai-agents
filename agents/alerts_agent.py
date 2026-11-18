"""Telegram alerts: DISABLED unless repo secrets TELEGRAM_TOKEN and TELEGRAM_CHAT_ID (or CHAT_ID)
exist. Sends only NEW scanner signals compared with the previous run."""
from __future__ import annotations

import os

import requests


def configured() -> bool:
    return bool(os.environ.get("TELEGRAM_TOKEN") and
                (os.environ.get("TELEGRAM_CHAT_ID") or os.environ.get("CHAT_ID")))


def send_new_signals(current: list[dict], previous: list[dict], page_url: str) -> dict:
    if not configured():
        return {"status": "disabled", "reason": "لم تُضف أسرار TELEGRAM_TOKEN و TELEGRAM_CHAT_ID"}
    prev = {(x["symbol"], x["tf"], x["side"], x.get("bar_time")) for x in previous}
    new = [x for x in current if (x["symbol"], x["tf"], x["side"], x.get("bar_time")) not in prev]
    if not new:
        return {"status": "ok", "sent": 0}
    tf_ar = {"1d": "يومي", "4h": "4 ساعات"}
    lines = ["إشارات جديدة من الماسح (ليست توصية):"]
    lines += [f"• {x['symbol']} — {x['side']} — {tf_ar.get(x['tf'], x['tf'])} — إغلاق {x['close']}" for x in new]
    lines.append(page_url)
    token = os.environ["TELEGRAM_TOKEN"]
    chat = os.environ.get("TELEGRAM_CHAT_ID") or os.environ.get("CHAT_ID")
    r = requests.post(f"https://api.telegram.org/bot{token}/sendMessage",
                      data={"chat_id": chat, "text": "\n".join(lines)}, timeout=20)
    return {"status": "ok" if r.ok else "error", "sent": len(new) if r.ok else 0,
            "http": r.status_code}
