"""Exhaustive live test: every symbol x every timeframe x every agent tab.
Usage: python full_matrix_test.py URL OUTDIR"""
import json
import sys
import time
from playwright.sync_api import sync_playwright

URL, OUT = sys.argv[1], sys.argv[2]
TFS = ["1d", "4h", "1h"]
SYM_TABS = ["summary", "plan", "data", "technical", "patterns", "levels", "news", "sentiment",
            "fundamentals", "options", "backtest", "risk"]
TF_TABS = {"plan", "data", "technical", "patterns", "levels"}
GLOBAL_TABS = ["crypto", "macro", "scanner", "status"]


def check_tab(tab, txt, kind, etf, html):
    fail_words = ("فشل هذا الوكيل" in txt) or ("لا توجد بيانات" in txt)
    if fail_words:
        return False, "agent failure text"
    if tab == "summary":
        ok = "الملخص العربي" in txt and len(txt) > 80 and "لا يوجد ملخص" not in txt
        return ok, ""
    if tab == "plan":
        return ("خطة الصفقة الآلية" in txt and "فحص تاريخي" in txt and "الحالة" in txt), ""
    if tab == "data":
        return ("آخر سعر" in txt and "عدد الشموع" in txt), ""
    if tab == "technical":
        return ("الاتجاه" in txt and "RSI 14" in txt and "الدعوم" in txt), ""
    if tab == "patterns":
        return ("أنماط الشموع" in txt and "يعمل" in txt), ""
    if tab == "levels":
        return ("الموجة" in txt and "0.618" in txt), ""
    if tab == "news":
        n = html.count("<li>")
        return n >= 1, f"{n} headlines"
    if tab == "sentiment":
        return ("المحصلة" in txt and "FinBERT" in txt), ""
    if tab == "fundamentals":
        if kind == "crypto" or etf:
            return ("غير متاح" in txt), "n/a expected"
        return ("الإيرادات" in txt and "ربحية السهم" in txt and "يعمل" in txt), ""
    if tab == "options":
        if kind == "crypto":
            return ("غير متاح" in txt), "n/a expected"
        return ("أقرب انتهاء" in txt and "نسبة بوت/كول" in txt), ""
    if tab == "backtest":
        return ("الصفقات" in txt and "الرابحة" in txt and "الخاسرة" in txt), ""
    if tab == "risk":
        return ("مبلغ المخاطرة" in txt), ""
    return len(txt) > 40, ""


res = {"cells": [], "global": [], "console_errors": []}
with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/usr/bin/google-chrome", args=["--no-sandbox"])
    pg = b.new_page(viewport={"width": 1440, "height": 900})
    pg.on("pageerror", lambda e: res["console_errors"].append("pageerror: " + str(e)))
    pg.on("console", lambda m: m.type == "error" and res["console_errors"].append("console: " + m.text))
    pg.goto(URL, wait_until="networkidle")
    pg.wait_for_selector("body[data-ready='1']", timeout=30000)
    syms = pg.evaluate("window.__app.state.index.symbols.map(s=>({symbol:s.symbol,kind:s.kind}))")
    # tick swings toggle on so all overlay types are exercised
    pg.check("#tgSwings")
    for s in syms:
        sym = s["symbol"]
        pg.select_option("#symbolSelect", sym)
        pg.wait_for_function(f"window.__app.state.data['{sym}'] && window.__app.state.sym==='{sym}'", timeout=20000)
        etf = pg.evaluate(f"!!window.__app.state.data['{sym}'].etf")
        for tf in TFS:
            pg.click(f".tf[data-tf='{tf}']")
            pg.wait_for_timeout(250)
            info = pg.evaluate("""(()=>{const st=window.__app.state;const d=st.candle.data();
              const t=st.data[st.sym].tf[st.tf];
              return {n:d.length,last:d.length?d[d.length-1].time:null,lastClose:d.length?d[d.length-1].close:null,
                jsonLast:t.bars[t.bars.length-1][0],jsonClose:t.bars[t.bars.length-1][4],
                lines:st.lines.length,planLines:st.planLines.length,markers:st.candle.markers().length,
                sup:(t.technical.supports||[]).length,res:(t.technical.resistances||[]).length,
                canv:document.querySelectorAll('#chart canvas').length}})()""")
            exp_lines = info["sup"] + info["res"] + info["planLines"]  # S/R + trade-plan lines
            ok = info["n"] > 0 and info["canv"] > 0 and info["last"] == info["jsonLast"] and \
                info["lastClose"] == info["jsonClose"] and info["lines"] == exp_lines and info["markers"] > 0
            res["cells"].append({"symbol": sym, "tf": tf, "part": f"chart {tf}", "ok": ok, "info": info})
            for tab in SYM_TABS:
                if tf != "1d" and tab not in TF_TABS:
                    continue
                pg.click(f".tab[data-tab='{tab}']")
                pg.wait_for_timeout(60)
                txt = pg.inner_text("#tabBody")
                html = pg.inner_html("#tabBody")
                good, note = check_tab(tab, txt, s["kind"], etf, html)
                res["cells"].append({"symbol": sym, "tf": tf, "part": tab, "ok": good, "note": note,
                                     "snippet": txt.replace("\n", " ")[:160]})
        print(sym, "done", flush=True)
    for tab in GLOBAL_TABS:
        pg.click(f".tab[data-tab='{tab}']")
        pg.wait_for_timeout(100)
        txt = pg.inner_text("#tabBody")
        ok = len(txt) > 40 and "فشل هذا الوكيل" not in txt
        if tab == "scanner":
            ok = ok and f"فُحص {len(syms)}" in txt
        if tab == "crypto":
            ok = ok and all(x in txt for x in ("BTCUSDT", "ETHUSDT", "SOLUSDT"))
        res["global"].append({"part": tab, "ok": ok, "snippet": txt.replace("\n", " ")[:200]})
    b.close()

json.dump(res, open(f"{OUT}/full_matrix.json", "w"), ensure_ascii=False, indent=1)
cells = res["cells"]
fails = [c for c in cells if not c["ok"]] + [g for g in res["global"] if not g["ok"]]
print("cells", len(cells) + len(res["global"]), "fail", len(fails), "console errors", len(res["console_errors"]))
for f in fails:
    print("FAIL", json.dumps(f, ensure_ascii=False)[:400])
for e in res["console_errors"][:10]:
    print("ERR", e[:300])
