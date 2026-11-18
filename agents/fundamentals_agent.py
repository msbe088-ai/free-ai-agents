"""Fundamentals / earnings agent: SEC EDGAR companyfacts (official filings, declared
User-Agent required) + next earnings date from Yahoo (yfinance)."""
from __future__ import annotations

import time
from datetime import datetime, timezone

import yfinance as yf

from .common import http_get, ok, fail, na, r2, retry_call

SOURCE = "SEC EDGAR companyfacts + Yahoo (موعد الأرباح)"
_cik_map: dict | None = None

REVENUE_TAGS = ["RevenueFromContractWithCustomerExcludingAssessedTax", "Revenues",
                "SalesRevenueNet", "RevenuesNetOfInterestExpense"]


def _headers(ua: str) -> dict:
    return {"User-Agent": ua, "Accept-Encoding": "gzip, deflate"}


def _cik(symbol: str, ua: str) -> str | None:
    global _cik_map
    if _cik_map is None:
        r = http_get("https://www.sec.gov/files/company_tickers.json", headers=_headers(ua))
        _cik_map = {v["ticker"].upper(): str(v["cik_str"]).zfill(10) for v in r.json().values()}
    return _cik_map.get(symbol.upper().replace("-", "."))


def _quarters(facts: dict, tags: list[str], unit: str, n: int = 5):
    """Latest discrete-quarter values (duration ~3 months) from 10-Q/10-K filings."""
    gaap = facts.get("facts", {}).get("us-gaap", {})
    best = (None, [])
    for tag in tags:
        units = gaap.get(tag, {}).get("units", {}).get(unit)
        if not units:
            continue
        rows = {}
        for u in units:
            if "start" not in u or u.get("form") not in ("10-Q", "10-K"):
                continue
            days = (datetime.fromisoformat(u["end"]) - datetime.fromisoformat(u["start"])).days
            if 80 <= days <= 100:
                rows[u["end"]] = {"end": u["end"], "value": u["val"], "form": u["form"],
                                  "filed": u["filed"], "fy": u.get("fy"), "fp": u.get("fp")}
        if rows:
            out = [rows[k] for k in sorted(rows)][-n:]
            if not best[1] or out[-1]["end"] > best[1][-1]["end"]:
                best = (tag, out)
    return best


def fetch(symbol: str, is_etf: bool, ua: str) -> dict:
    if is_etf:
        return na("صندوق متداول (ETF): لا توجد قوائم شركة في EDGAR")
    try:
        cik = _cik(symbol, ua)
        if not cik:
            return na("الرمز غير موجود في قائمة SEC")
        time.sleep(0.2)  # stay far below SEC's 10 req/s
        facts = http_get(f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json",
                         headers=_headers(ua), timeout=40).json()
        rev_tag, rev = _quarters(facts, REVENUE_TAGS, "USD")
        _, ni = _quarters(facts, ["NetIncomeLoss"], "USD")
        _, eps = _quarters(facts, ["EarningsPerShareDiluted"], "USD/shares")

        def pack(rows, scale=1e9, nd=2):
            return [{"end": x["end"], "value": r2(x["value"] / scale, nd), "form": x["form"],
                     "filed": x["filed"]} for x in rows]
        data = {"entity": facts.get("entityName"), "cik": cik,
                "revenue_bn": pack(rev), "net_income_bn": pack(ni),
                "eps_diluted": pack(eps, 1, 2), "revenue_tag": rev_tag,
                "note": "أرقام آخر أرباع مُفصح عنها في إيداعات SEC (الربع الرابع غالباً داخل التقرير السنوي فلا يظهر منفصلاً)"}
        # Next earnings date from Yahoo
        try:
            cal = retry_call(lambda: yf.Ticker(symbol).calendar, retries=2, base_sleep=3)
            ed = cal.get("Earnings Date") if isinstance(cal, dict) else None
            if ed:
                data["next_earnings"] = [str(x) for x in (ed if isinstance(ed, list) else [ed])]
                data["eps_estimate_avg"] = r2(cal.get("Earnings Average"))
        except Exception as e:  # noqa: BLE001
            data["next_earnings_error"] = str(e)[:150]
        last_filed = max((x["filed"] for x in rev + ni + eps), default=None)
        dt = datetime.fromisoformat(last_filed).replace(tzinfo=timezone.utc) if last_filed else None
        return ok(data, SOURCE, dt)
    except Exception as e:  # noqa: BLE001
        return fail(SOURCE, e)
