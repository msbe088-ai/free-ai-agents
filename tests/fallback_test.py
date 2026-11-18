"""Simulate source failures and check the last-good-data fallback (no invented data).
Run from repo root: PYTHONPATH=. python tests/fallback_test.py OUTDIR"""
import json
import sys

import run
from agents import data_agent, news_agent

out = sys.argv[1]
real_fetch, real_news = data_agent.fetch, news_agent.fetch


def bad_fetch(sym):
    if sym == "AAPL":
        raise RuntimeError("simulated Yahoo 429")
    return real_fetch(sym)


def bad_news(sym, limit=10):
    if sym == "MSFT":
        return {"status": "error", "source": "Yahoo Finance RSS", "error": "simulated RSS 429"}
    return real_news(sym, limit)


data_agent.fetch = bad_fetch
news_agent.fetch = bad_news
sys.argv = ["run.py", "--out", out, "--only", "AAPL,MSFT", "--no-llm", "--no-finbert"]
run.main()
a = json.load(open(f"{out}/data/sym/AAPL.json", encoding="utf-8"))
m = json.load(open(f"{out}/data/sym/MSFT.json", encoding="utf-8"))
print("AAPL stale:", a.get("stale"), "|", a.get("stale_reason"), "| bars kept:", len(a["tf"]["1d"]["bars"]),
      "| generated_at (original):", a.get("generated_at_label"))
print("MSFT news stale:", m["news"].get("stale"), "|", m["news"].get("stale_reason"), "| items:", len(m["news"].get("items", [])),
      "| original fetch:", m["news"].get("fetched_at_label"))
