"""Shared helpers: HTTP with retries/backoff, time labels, JSON-safe output."""
from __future__ import annotations

import json
import math
import random
import time
from datetime import datetime, timezone, timedelta

import requests

RIYADH = timezone(timedelta(hours=3))
UA_DEFAULT = "free-ai-agents/1.0 (+https://github.com/msbe088-ai/free-ai-agents)"
UA_BROWSER = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def riyadh_label(dt: datetime | None) -> str | None:
    """'2026-11-18 03:10 بتوقيت الرياض' from an aware or UTC-naive datetime."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(RIYADH).strftime("%Y-%m-%d %H:%M") + " بتوقيت الرياض"


def iso(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat(timespec="seconds")


def http_get(url: str, *, headers: dict | None = None, params: dict | None = None,
             timeout: float = 20, retries: int = 4, base_sleep: float = 2.0) -> requests.Response:
    """GET with exponential backoff + jitter; honours Retry-After on 429/5xx."""
    h = {"User-Agent": UA_DEFAULT}
    if headers:
        h.update(headers)
    last_exc: Exception | None = None
    for attempt in range(retries):
        try:
            r = requests.get(url, headers=h, params=params, timeout=timeout)
            if r.status_code == 200:
                return r
            if r.status_code in (429, 500, 502, 503, 504):
                ra = r.headers.get("Retry-After")
                wait = float(ra) if ra and ra.isdigit() else base_sleep * (2 ** attempt)
                last_exc = RuntimeError(f"HTTP {r.status_code} for {url}")
                time.sleep(min(wait, 60) + random.random())
                continue
            raise RuntimeError(f"HTTP {r.status_code} for {url}")
        except requests.RequestException as e:  # network error -> retry
            last_exc = e
            time.sleep(base_sleep * (2 ** attempt) + random.random())
    raise RuntimeError(f"failed after {retries} tries: {last_exc}")


def retry_call(fn, *args, retries: int = 4, base_sleep: float = 3.0, **kwargs):
    """Retry any callable (e.g. yfinance) with exponential backoff."""
    last = None
    for attempt in range(retries):
        try:
            out = fn(*args, **kwargs)
            return out
        except Exception as e:  # noqa: BLE001
            last = e
            time.sleep(base_sleep * (2 ** attempt) + random.random())
    raise RuntimeError(f"failed after {retries} tries: {last}")


def r2(x, nd: int = 2):
    """Round finite floats; None for NaN/inf."""
    if x is None:
        return None
    try:
        f = float(x)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(f):
        return None
    return round(f, nd)


def price_round(x):
    """Price rounding that keeps precision for cheap assets."""
    if x is None:
        return None
    f = float(x)
    if not math.isfinite(f):
        return None
    a = abs(f)
    nd = 2 if a >= 1 else 4 if a >= 0.01 else 6
    return round(f, nd)


def dump_json(path, obj) -> None:
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, ensure_ascii=False, separators=(",", ":"), allow_nan=False)


def ok(data: dict, source: str, data_time: datetime | None = None) -> dict:
    return {"status": "ok", "source": source, "fetched_at": iso(now_utc()),
            "fetched_at_label": riyadh_label(now_utc()),
            "data_time": iso(data_time), "data_time_label": riyadh_label(data_time), **data}


def fail(source: str, err: Exception | str) -> dict:
    return {"status": "error", "source": source, "error": str(err)[:300],
            "fetched_at": iso(now_utc()), "fetched_at_label": riyadh_label(now_utc())}


def na(reason: str) -> dict:
    return {"status": "na", "reason": reason}
