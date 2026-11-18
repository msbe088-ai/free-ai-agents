"""Trade-plan test: every symbol x timeframe. Usage: python plan_test.py URL OUTDIR"""
import json, sys
from playwright.sync_api import sync_playwright
URL, OUT = sys.argv[1], sys.argv[2]
rows, errs = [], []
with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/usr/bin/google-chrome", args=["--no-sandbox"])
    pg = b.new_page(viewport={"width": 1440, "height": 900})
    pg.on("pageerror", lambda e: errs.append("pageerror: " + str(e)))
    pg.on("console", lambda m: m.type == "error" and errs.append("console: " + m.text))
    pg.goto(URL, wait_until="networkidle"); pg.wait_for_selector("body[data-ready='1']", timeout=30000)
    syms = pg.evaluate("window.__app.state.index.symbols.map(s=>s.symbol)")
    for sym in syms:
        pg.select_option("#symbolSelect", sym)
        pg.wait_for_function(f"window.__app.state.sym==='{sym}' && window.__app.state.data['{sym}']", timeout=20000)
        for tf in ("1d", "4h", "1h"):
            pg.click(f".tf[data-tf='{tf}']"); pg.wait_for_timeout(200)
            pg.click(".tab[data-tab='plan']"); pg.wait_for_timeout(80)
            txt = pg.inner_text("#tabBody")
            p_ = pg.evaluate("(()=>{const st=window.__app.state;return st.data[st.sym].tf[st.tf].plan})()")
            n_plan = pg.evaluate("window.__app.state.planLines.length")
            ok, note = True, []
            if not p_ or p_.get("status") != "ok":
                ok = False; note.append("no plan")
            else:
                h = p_["history"]
                if h["wins"] + h["losses"] != h["trades"]:
                    ok = False; note.append("hist sum")
                if p_["side"] == "none":
                    if n_plan != 0: ok = False; note.append("lines drawn for no-trade")
                    if "لا صفقة" not in txt: ok = False; note.append("no-trade text")
                else:
                    e, s = p_["entry"], p_["stop"]; tg = [t["price"] for t in p_["targets"]]
                    seq = [s, e] + tg
                    mono = all(x < y for x, y in zip(seq, seq[1:])) if p_["side"] == "buy" else all(x > y for x, y in zip(seq, seq[1:]))
                    if not mono: ok = False; note.append(f"order {seq}")
                    if n_plan != 2 + len(tg): ok = False; note.append(f"lines {n_plan}")
                    if len(tg) < 2: note.append(f"only {len(tg)} target(s)")
                    rr = [t["r"] for t in p_["targets"]]
                    calc = [round(abs(t - e) / abs(e - s), 2) for t in tg]
                    if any(abs(a - c) > 0.02 for a, c in zip(rr, calc)): ok = False; note.append(f"R {rr} vs {calc}")
                    if "الدخول" not in txt or "الوقف" not in txt: ok = False; note.append("tab text")
            # toggle test
            pg.uncheck("#tgPlan"); pg.wait_for_timeout(80)
            off = pg.evaluate("window.__app.state.planLines.length")
            pg.check("#tgPlan"); pg.wait_for_timeout(80)
            on = pg.evaluate("window.__app.state.planLines.length")
            if off != 0 or on != n_plan: ok = False; note.append(f"toggle off={off} on={on}")
            rows.append({"symbol": sym, "tf": tf, "ok": ok, "side": p_ and p_.get("side"), "status": p_ and p_.get("status_ar"),
                         "entry": p_ and p_.get("entry"), "stop": p_ and p_.get("stop"),
                         "targets": p_ and [t["price"] for t in p_.get("targets", [])], "lines": n_plan,
                         "history": p_ and p_.get("history"), "note": "; ".join(note)})
    # question routing
    qa = []
    for q, sym in (("وش خطة الدخول والخروج لأبل؟", "AAPL"), ("وين الأهداف القريبة والبعيدة للبيتكوين", "BTC"), ("متى ادخل تسلا", "TSLA")):
        pg.fill("#askInput", q); pg.click(".ask-form button"); pg.wait_for_timeout(700)
        qa.append({"q": q, "topic": pg.get_attribute("#askAnswer", "data-topic"), "symbol": pg.get_attribute("#askAnswer", "data-symbol"),
                   "ok": pg.get_attribute("#askAnswer", "data-topic") == "plan" and pg.get_attribute("#askAnswer", "data-symbol") == sym,
                   "answer": pg.inner_text("#askAnswer")[:300]})
    # summary mentions plan
    summ = pg.evaluate("""(async()=>{const o={};for(const s of window.__app.state.index.symbols){const d=await (await fetch('data/sym/'+s.symbol+'.json')).json();o[s.symbol]={mode:d.summary&&d.summary.mode,plan:!!(d.summary&&/خط[ةه]/.test(d.summary.text))}}return o})()""")
    # mobile
    m = b.new_page(viewport={"width": 390, "height": 844}, device_scale_factor=2, is_mobile=True)
    merr = []
    m.on("pageerror", lambda e: merr.append(str(e))); m.on("console", lambda x: x.type == "error" and merr.append(x.text))
    target = next((r for r in rows if r["tf"] == "1d" and r["side"] in ("buy", "sell")), rows[0])
    m.goto(URL + "#" + target["symbol"], wait_until="networkidle"); m.wait_for_selector("body[data-ready='1']"); m.wait_for_timeout(1200)
    mlines = m.evaluate("window.__app.state.planLines.length")
    sw = m.evaluate("document.documentElement.scrollWidth")
    m.locator("#chart").scroll_into_view_if_needed()
    m.screenshot(path=f"{OUT}/mobile_plan_{target['symbol']}_1d.png")
    m.click(".tab[data-tab='plan']"); m.wait_for_timeout(200)
    m.screenshot(path=f"{OUT}/mobile_plan_full_{target['symbol']}.png", full_page=True)
    b.close()
res = {"rows": rows, "qa": qa, "summary": summ, "errors": errs,
       "mobile": {"symbol": target["symbol"], "plan_lines": mlines, "scrollWidth": sw, "errors": merr}}
json.dump(res, open(f"{OUT}/plan_test.json", "w"), ensure_ascii=False, indent=1)
print("cells", len(rows), "fail", sum(not r["ok"] for r in rows), "| qa ok", sum(q["ok"] for q in qa), "/", len(qa),
      "| console errors", len(errs), "| mobile", res["mobile"])
for r in rows:
    if not r["ok"] or r["note"]:
        print(("FAIL " if not r["ok"] else "NOTE ") + json.dumps(r, ensure_ascii=False)[:300])
for q in qa: print(q["ok"], q["q"], "->", q["topic"], q["symbol"])
print(json.dumps(summ, ensure_ascii=False))
