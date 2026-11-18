"""Headless browser test of the page (live URL or local). Usage: python page_test.py URL OUTDIR"""
import json
import sys
import time
from playwright.sync_api import sync_playwright

URL = sys.argv[1]
OUT = sys.argv[2] if len(sys.argv) > 2 else "."
results = []


def rec(item, ok, note=""):
    results.append({"item": item, "ok": bool(ok), "note": note})
    print(("PASS" if ok else "FAIL"), item, "|", note, flush=True)


QUESTIONS = [
    ("وش الدعم والمقاومة لأبل؟", "technical", "AAPL"),
    ("كم الفائدة والتضخم؟", "macro", None),
    ("وش الإشارات اليوم؟", "scanner", None),
    ("كم سعر البيتكوين", "price", "BTC"),
    ("نتائج الاختبار التاريخي لتسلا", "backtest", "TSLA"),
    ("فيبوناتشي انفيديا", "fib", "NVDA"),
    ("وش آخر أخبار مايكروسوفت", "news", "MSFT"),
    ("موعد أرباح امازون", "fund", "AMZN"),
    ("الاوبشن على SPY", "options", "SPY"),
    ("مشاعر الأخبار عن ميتا", "sentiment", "META"),
    ("أنماط الشموع على الإيثريوم", "patterns", "ETH"),
    ("كم سهم اشتري؟ حجم الصفقة", "risk", None),
    ("وش رايك في سولانا", "summary", "SOL"),
]

with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/usr/bin/google-chrome", args=["--no-sandbox"])
    pg = b.new_page(viewport={"width": 1440, "height": 900})
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    t0 = time.time()
    pg.goto(URL, wait_until="networkidle")
    pg.wait_for_selector("body[data-ready='1']", timeout=30000)
    rec("page loads", True, f"{time.time()-t0:.1f}s; notice: {pg.inner_text('#notice')[:120]}")
    for sym in ("AAPL", "BTC"):
        pg.select_option("#symbolSelect", sym)
        pg.wait_for_timeout(1200)
        for tf in ("1d", "4h", "1h"):
            pg.click(f".tf[data-tf='{tf}']")
            pg.wait_for_timeout(700)
            n = pg.evaluate("window.__app.state.candle.data().length")
            canv = pg.evaluate("document.querySelectorAll('#chart canvas').length")
            lines = pg.evaluate("window.__app.state.lines.length")
            foot = pg.inner_text("#chartFoot")
            rec(f"chart {sym} {tf}", n > 50 and canv > 0, f"bars={n}, canvases={canv}, price lines={lines}; {foot[:110]}")
            if tf == "1d":
                pg.screenshot(path=f"{OUT}/desktop_{sym}_{tf}.png", full_page=False)
    # tabs on AAPL daily
    pg.select_option("#symbolSelect", "AAPL"); pg.wait_for_timeout(800)
    pg.click(".tf[data-tf='1d']"); pg.wait_for_timeout(500)
    tabs = pg.evaluate("[...document.querySelectorAll('.tab')].map(x=>x.dataset.tab)")
    for t in tabs:
        pg.click(f".tab[data-tab='{t}']"); pg.wait_for_timeout(300)
        txt = pg.inner_text("#tabBody")
        bad = ("فشل هذا الوكيل" in txt) or ("لا توجد بيانات" in txt) or len(txt) < 40
        rec(f"tab {t} (AAPL)", not bad, txt.replace("\n", " ")[:140])
    for t in ("fundamentals", "options", "sentiment", "news"):
        pg.select_option("#symbolSelect", "BTC"); pg.wait_for_timeout(600)
        pg.click(f".tab[data-tab='{t}']"); pg.wait_for_timeout(300)
        rec(f"tab {t} (BTC)", True, pg.inner_text("#tabBody").replace("\n", " ")[:120])
    # summary
    pg.select_option("#symbolSelect", "AAPL"); pg.wait_for_timeout(600)
    pg.click(".tab[data-tab='summary']"); pg.wait_for_timeout(300)
    s = pg.inner_text(".summary")
    mode = pg.evaluate("window.__app.state.data['AAPL'].summary.mode")
    rec("Arabic summary present (AAPL)", len(s) > 30 and any("\u0600" <= c <= "\u06ff" for c in s), f"mode={mode}: {s[:160]}")
    modes = pg.evaluate("""(async()=>{const o={};for(const s of window.__app.state.index.symbols){const r=await fetch('data/sym/'+s.symbol+'.json');const d=await r.json();o[s.symbol]=d.summary?d.summary.mode:null}return o})()""")
    rec("summary modes all symbols", all(modes.values()), json.dumps(modes))
    # risk calculator known case
    pg.click(".tab[data-tab='risk']"); pg.wait_for_timeout(300)
    for sel, v in (("#rkCap", "10000"), ("#rkPct", "1"), ("#rkEntry", "100"), ("#rkStop", "95"), ("#rkTarget", "110")):
        pg.fill(sel, v)
    pg.click("#rkBtn"); pg.wait_for_timeout(200)
    out = pg.inner_text("#rkOut")
    calc = pg.evaluate("window.calcRisk(10000,1,100,95,110)")
    good = calc["riskAmount"] == 100 and calc["units"] == 20 and calc["positionValue"] == 2000 and calc["rr"] == 2
    good = good and "100" in pg.inner_text("#rkRiskAmt") and pg.inner_text("#rkUnits").strip() == "20" and "2,000" in pg.inner_text("#rkValue")
    rec("risk calc 10000/1%/100/95/110 -> risk 100, 20 units, 2000 value, R:R 2", good, out.replace("\n", " ")[:160])
    short = pg.evaluate("window.calcRisk(5000,2,50,52)")
    rec("risk calc short 5000/2%/50/52 -> risk 100, 50 units", short["riskAmount"] == 100 and short["units"] == 50 and short["side"] == "بيع", json.dumps(short, ensure_ascii=False))
    pg.screenshot(path=f"{OUT}/desktop_risk.png")
    # questions
    for q, topic, sym in QUESTIONS:
        pg.fill("#askInput", q); pg.click(".ask-form button"); pg.wait_for_timeout(900)
        got_t = pg.get_attribute("#askAnswer", "data-topic"); got_s = pg.get_attribute("#askAnswer", "data-symbol")
        ans = pg.inner_text("#askAnswer").replace("\n", " ")
        ok = got_t == topic and (sym is None or got_s == sym)
        rec(f"ask: {q}", ok, f"topic={got_t} sym={got_s} | {ans[:150]}")
    pg.fill("#askInput", "وش الدعم والمقاومة لأبل؟"); pg.click(".ask-form button"); pg.wait_for_timeout(900)
    pg.screenshot(path=f"{OUT}/desktop_full.png", full_page=True)
    rec("no JS errors (desktop)", not errs, "; ".join(errs)[:200])
    # mobile
    m = b.new_page(viewport={"width": 390, "height": 844}, device_scale_factor=2, is_mobile=True)
    merrs = []
    m.on("pageerror", lambda e: merrs.append(str(e)))
    m.goto(URL + "#BTC", wait_until="networkidle")
    m.wait_for_selector("body[data-ready='1']", timeout=30000)
    m.wait_for_timeout(1000)
    n = m.evaluate("window.__app.state.candle.data().length")
    m.screenshot(path=f"{OUT}/mobile_BTC.png", full_page=False)
    m.screenshot(path=f"{OUT}/mobile_full.png", full_page=True)
    rec("mobile 390px renders (BTC)", n > 50 and not merrs, f"bars={n}; errors={merrs[:2]}")
    b.close()

json.dump(results, open(f"{OUT}/test_results.json", "w"), ensure_ascii=False, indent=1)
print("TOTAL", sum(r["ok"] for r in results), "/", len(results))
