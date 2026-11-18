"""Orchestrator: runs every agent over the watchlist and writes static JSON for the page.

Never invents data: any failed section falls back to the LAST GOOD output of the previous
run (downloaded from the live page) and is flagged stale with its original timestamp;
if there is no previous output, the section shows the error.
"""
from __future__ import annotations

import argparse
import gc
import json
import os
import sys
import time
import traceback
from pathlib import Path

import pandas as pd
import requests
import yaml

from agents import (plan_agent, alerts_agent, backtest_agent, crypto_agent, data_agent, explainer_agent,
                    fundamentals_agent, levels_agent, macro_agent, news_agent, options_agent,
                    patterns_agent, scanner_agent, sentiment_agent, technical_agent)
from agents.common import dump_json, iso, now_utc, price_round, r2, riyadh_label

ROOT = Path(__file__).parent
TFS = ("1d", "4h", "1h")


def log(*a):
    print(f"[{time.strftime('%H:%M:%S')}]", *a, flush=True)


def pages_base() -> str:
    if os.environ.get("PAGES_BASE"):
        return os.environ["PAGES_BASE"].rstrip("/") + "/"
    repo = os.environ.get("GITHUB_REPOSITORY", "msbe088-ai/free-ai-agents")
    owner, name = repo.split("/")
    return f"https://{owner.lower()}.github.io/{name}/"


def get_prev(base: str, rel: str) -> dict | None:
    try:
        r = requests.get(base + rel, timeout=20)
        if r.status_code == 200:
            return r.json()
    except Exception:  # noqa: BLE001
        pass
    return None


def make_tkey(tf: str, kind: str):
    if tf == "1d":
        tz = "America/New_York" if kind == "stock" else "UTC"
        return lambda ts: pd.Timestamp(ts).tz_convert(tz).strftime("%Y-%m-%d")
    return lambda ts: int(pd.Timestamp(ts).timestamp()) + 3 * 3600  # shown in Riyadh time


def bars_json(df: pd.DataFrame, tkey, n: int) -> list:
    d = df.iloc[-n:]
    return [[tkey(ts), price_round(o), price_round(h), price_round(l), price_round(c),
             r2(v, 0)] for ts, o, h, l, c, v in
            zip(d.index, d["open"], d["high"], d["low"], d["close"], d["volume"])]


def section(fn, prev_sec, name, errors):
    """Run one agent section; on error reuse previous good output (flagged stale)."""
    try:
        out = fn()
        if isinstance(out, dict) and out.get("status") == "error":
            raise RuntimeError(out.get("error"))
        if isinstance(out, dict) and "status" not in out:
            out["status"] = "ok"
        return out
    except Exception as e:  # noqa: BLE001
        errors.append(f"{name}: {str(e)[:200]}")
        if prev_sec and prev_sec.get("status") == "ok":
            p = dict(prev_sec)
            p["stale"] = True
            p["stale_reason"] = f"فشل التحديث ({str(e)[:120]})؛ هذه آخر بيانات ناجحة"
            return p
        return {"status": "error", "error": str(e)[:300]}


def process_symbol(item: dict, kind: str, cfg: dict, prev: dict | None, sec_ua: str | None) -> dict:
    sym = item["symbol"]
    display = item.get("display", sym)
    errors: list[str] = []
    out = {"symbol": display, "ticker": sym, "name": item["name"], "kind": kind,
           "etf": bool(item.get("etf")), "ar": item.get("ar", []),
           "generated_at": iso(now_utc()), "generated_at_label": riyadh_label(now_utc()),
           "tf": {}, "signals": {}, "tf_close": {}, "tf_bar": {}, "errors": errors}
    prev = prev or {}
    n_chart = int(cfg["settings"].get("bars_on_chart", 500))
    try:
        data = crypto_agent.fetch(sym) if kind == "crypto" else data_agent.fetch(sym)
    except Exception as e:  # noqa: BLE001
        errors.append(f"bars: {e}")
        data = None
    if data is None:
        if prev.get("tf"):
            prev["stale"] = True
            prev["stale_reason"] = "فشل جلب الأسعار في هذا التشغيل؛ المعروض آخر بيانات ناجحة"
            prev.setdefault("errors", []).extend(errors)
            return prev
        out["status"] = "error"
        return out

    for tf in TFS:
        df = data[tf]
        forming = bool(data["forming"][tf])
        closed = df.iloc[:-1] if forming else df
        tkey = make_tkey(tf, kind)
        p_tf = (prev.get("tf") or {}).get(tf, {})
        last_ts = df.index[-1]
        t = {"source": data["source"], "bars": bars_json(df, tkey, n_chart),
             "last_bar_forming": forming,
             "last_bar_time_label": (f"شمعة يوم {tkey(last_ts)} (تاريخ السوق)" if tf == "1d"
                                     else "افتتاح الشمعة " + riyadh_label(last_ts.to_pydatetime())),
             "last_close": price_round(df["close"].iloc[-1]),
             "fetched_at_label": riyadh_label(now_utc())}
        t["technical"] = section(lambda: technical_agent.analyse(closed, tkey), p_tf.get("technical"), f"technical {tf}", errors)
        t["patterns"] = section(lambda: patterns_agent.analyse(closed, tkey), p_tf.get("patterns"), f"patterns {tf}", errors)
        t["levels"] = section(lambda: levels_agent.analyse(closed, tkey), p_tf.get("levels"), f"levels {tf}", errors)
        trend = (t["technical"] or {}).get("trend", "") if t["technical"].get("status") == "ok" else ""
        t["plan"] = section(lambda: plan_agent.analyse(closed, tkey, trend), p_tf.get("plan"), f"plan {tf}", errors)
        out["tf"][tf] = t
        if tf in ("1d", "4h"):
            out["signals"][tf] = scanner_agent.current_signal(closed)
            out["tf_close"][tf] = price_round(closed["close"].iloc[-1])
            out["tf_bar"][tf] = tkey(closed.index[-1])
    d1 = data["1d"]
    closed1 = d1.iloc[:-1] if data["forming"]["1d"] else d1
    out["last"] = price_round(d1["close"].iloc[-1])
    out["change_pct"] = r2((d1["close"].iloc[-1] / d1["close"].iloc[-2] - 1) * 100)
    out["backtest"] = section(lambda: backtest_agent.run(closed1), prev.get("backtest"), "backtest", errors)
    news_sym = item.get("news", sym)
    out["news"] = section(lambda: news_agent.fetch(news_sym), prev.get("news"), "news", errors)
    if kind == "stock":
        out["options"] = section(lambda: options_agent.fetch(sym, float(d1["close"].iloc[-1])), prev.get("options"), "options", errors)
        if sec_ua:
            out["fundamentals"] = section(lambda: fundamentals_agent.fetch(sym, bool(item.get("etf")), sec_ua), prev.get("fundamentals"), "fundamentals", errors)
        else:
            out["fundamentals"] = {"status": "error", "error": "سر SEC_USER_AGENT غير موجود (SEC تطلب بريد تواصل)"}
    else:
        out["options"] = {"status": "na", "reason": "لا توجد سلسلة خيارات مجانية للكريبتو في هذا المصدر"}
        out["fundamentals"] = {"status": "na", "reason": "عملة رقمية: لا توجد قوائم مالية في SEC"}
    out["_prev_sentiment"] = prev.get("sentiment")
    out["_prev_summary"] = prev.get("summary")
    out["status"] = "ok"
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="site")
    ap.add_argument("--only", default="", help="comma-separated symbols (testing)")
    ap.add_argument("--no-llm", action="store_true")
    ap.add_argument("--no-finbert", action="store_true")
    args = ap.parse_args()
    t_start = time.time()
    started = now_utc()
    cfg = yaml.safe_load(open(ROOT / "config" / "watchlist.yml", encoding="utf-8"))
    outdir = Path(args.out)
    (outdir / "data" / "sym").mkdir(parents=True, exist_ok=True)
    base = pages_base()
    prev_index = get_prev(base, "data/index.json") or {}
    sec_ua = os.environ.get("SEC_USER_AGENT") or None
    only = {s.strip().upper() for s in args.only.split(",") if s.strip()}
    timings = {}

    items = [(x, "stock") for x in cfg.get("stocks", [])] + [(x, "crypto") for x in cfg.get("crypto", [])]
    if only:
        items = [(x, k) for x, k in items if x["symbol"].upper() in only or x.get("display", "").upper() in only]

    t0 = time.time()
    macro = macro_agent.fetch()
    if macro.get("status") != "ok" and (prev_index.get("macro") or {}).get("status") == "ok":
        macro = dict(prev_index["macro"], stale=True, stale_reason="فشل التحديث؛ آخر بيانات ناجحة")
    timings["macro"] = round(time.time() - t0, 1)
    log("macro", macro.get("status"))

    t0 = time.time()
    crypto_syms = [x["symbol"] for x, k in items if k == "crypto"]
    try:
        crypto24 = {"status": "ok", "source": crypto_agent.SOURCE, "fetched_at_label": riyadh_label(now_utc()),
                    "items": crypto_agent.ticker_24h(crypto_syms)} if crypto_syms else {"status": "na"}
    except Exception as e:  # noqa: BLE001
        crypto24 = {"status": "error", "error": str(e)[:200]}
    timings["crypto24"] = round(time.time() - t0, 1)

    results = []
    t0 = time.time()
    for item, kind in items:
        disp = item.get("display", item["symbol"])
        prev = get_prev(base, f"data/sym/{disp}.json")
        ts = time.time()
        try:
            r = process_symbol(item, kind, cfg, prev, sec_ua)
        except Exception as e:  # noqa: BLE001
            traceback.print_exc()
            r = prev or {"symbol": disp, "name": item["name"], "kind": kind, "status": "error", "errors": [str(e)]}
            r["stale"] = True
        log(disp, r.get("status"), f"{time.time()-ts:.1f}s", "errors:", len(r.get("errors", [])))
        results.append(r)
        time.sleep(1.0)  # be gentle with Yahoo
    timings["symbols"] = round(time.time() - t0, 1)

    # Sentiment (FinBERT, English only)
    t0 = time.time()
    run_fb = cfg["settings"].get("run_finbert", True) and not args.no_finbert
    for r in results:
        if r.get("status") != "ok" or "news" not in r:
            continue
        if not run_fb:
            r["sentiment"] = {"status": "na", "reason": "FinBERT معطّل في الإعدادات"}
            continue
        r["sentiment"] = section(lambda: sentiment_agent.score(r["news"]), r.get("_prev_sentiment"), "sentiment", r["errors"])
    sentiment_agent._pipe = None
    gc.collect()
    timings["sentiment"] = round(time.time() - t0, 1)
    log("sentiment done", timings["sentiment"])

    scan = scanner_agent.scan([r for r in results if r.get("status") == "ok"])

    # Arabic explainer (small local LLM)
    t0 = time.time()
    run_llm = cfg["settings"].get("run_llm", True) and not args.no_llm
    for r in results:
        if r.get("status") != "ok" or "tf" not in r:
            continue
        if r.get("stale") and r.get("summary"):
            continue
        r["summary"] = explainer_agent.explain(r, enabled=run_llm)
        r["summary"]["generated_at_label"] = riyadh_label(now_utc())
        log("summary", r["symbol"], r["summary"]["mode"])
    timings["explainer"] = round(time.time() - t0, 1)

    # Telegram alerts (disabled without secrets)
    prev_signals = (prev_index.get("scanner") or {}).get("signals", [])
    try:
        alerts = alerts_agent.send_new_signals(scan["signals"], prev_signals, base)
    except Exception as e:  # noqa: BLE001
        alerts = {"status": "error", "error": str(e)[:200]}

    # Write outputs
    agent_status = {}

    def count(name, getter):
        ok = err = stale = na = 0
        for r in results:
            try:
                s = getter(r)
            except Exception:  # noqa: BLE001
                s = None
            if not s:
                continue
            st = s.get("status")
            if s.get("stale"):
                stale += 1
            elif st == "ok":
                ok += 1
            elif st == "na":
                na += 1
            else:
                err += 1
        agent_status[name] = {"ok": ok, "error": err, "stale": stale, "na": na}
    stocks = lambda r: r.get("kind") == "stock"
    count("data", lambda r: {"status": "ok" if r.get("tf") else "error", "stale": r.get("stale")} if stocks(r) else None)
    count("crypto", lambda r: {"status": "ok" if r.get("tf") else "error", "stale": r.get("stale")} if not stocks(r) else None)
    count("technical", lambda r: r["tf"]["1d"]["technical"])
    count("patterns", lambda r: r["tf"]["1d"]["patterns"])
    count("levels", lambda r: r["tf"]["1d"]["levels"])
    count("plan", lambda r: r["tf"]["1d"].get("plan"))
    count("news", lambda r: r["news"])
    count("sentiment", lambda r: r["sentiment"])
    count("fundamentals", lambda r: r["fundamentals"] if stocks(r) else None)
    count("options", lambda r: r["options"] if stocks(r) else None)
    count("backtest", lambda r: r["backtest"])
    agent_status["explainer"] = {
        "llm": sum(1 for r in results if (r.get("summary") or {}).get("mode") == "llm"),
        "template": sum(1 for r in results if (r.get("summary") or {}).get("mode") == "template")}

    index_syms = []
    for r in results:
        r.pop("_prev_sentiment", None)
        r.pop("_prev_summary", None)
        dump_json(outdir / "data" / "sym" / f"{r['symbol']}.json", r)
        index_syms.append({"symbol": r["symbol"], "name": r.get("name"), "kind": r.get("kind"),
                           "ar": r.get("ar", []), "last": r.get("last"), "change_pct": r.get("change_pct"),
                           "status": r.get("status"), "stale": bool(r.get("stale")),
                           "signals": r.get("signals", {})})
    finished = now_utc()
    index = {"generated_at": iso(finished), "generated_at_label": riyadh_label(finished),
             "run_started_label": riyadh_label(started), "run_seconds": round(time.time() - t_start, 1),
             "timings": timings, "symbols": index_syms, "macro": macro, "crypto24": crypto24,
             "scanner": scan, "alerts": alerts, "agent_status": agent_status,
             "pages_base": base, "run_url": os.environ.get("RUN_URL"),
             "disclaimer": "بيانات مجانية وقد تكون متأخرة. ليست توصية بيع أو شراء."}
    dump_json(outdir / "data" / "index.json", index)
    log("DONE", index["run_seconds"], "s", json.dumps(agent_status, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
