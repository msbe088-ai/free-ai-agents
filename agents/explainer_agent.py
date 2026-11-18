"""Explainer agent: Qwen2.5-1.5B-Instruct Q4_K_M (GGUF, llama-cpp-python, CPU) writes a short
Arabic summary from the COMPUTED numbers only. A number guard rejects any figure that is not in
the facts; on rejection or if the model is unavailable, a fixed deterministic template is used."""
from __future__ import annotations

import os
import re
import time

REPO = "Qwen/Qwen2.5-1.5B-Instruct-GGUF"
FILE = "qwen2.5-1.5b-instruct-q4_k_m.gguf"
_llm = None
AR_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩٫", "0123456789.")


def load():
    global _llm
    if _llm is None:
        from huggingface_hub import hf_hub_download
        from llama_cpp import Llama
        path = hf_hub_download(REPO, FILE)
        _llm = Llama(model_path=path, n_ctx=2048, n_threads=os.cpu_count() or 4, verbose=False)
    return _llm


def _nums(text: str) -> list[float]:
    t = text.translate(AR_DIGITS).replace(",", "")
    return [float(x) for x in re.findall(r"-?\d+(?:\.\d+)?", t)]


def guard(text: str, facts: str) -> tuple[bool, list[float]]:
    allowed = _nums(facts)
    bad = []
    for n in _nums(text):
        if abs(n) <= 10 and float(n).is_integer():  # small counts / ordinals
            continue
        if not any(abs(n - a) <= max(0.011, abs(a) * 0.001) for a in allowed):
            bad.append(n)
    return (not bad), bad


def rsi_desc(v) -> str:
    if v is None:
        return "غير متوفر"
    return "تشبع بيعي (أقل من 30)" if v < 30 else "تشبع شرائي (أعلى من 70)" if v > 70 else "محايد (بين 30 و70)"


def facts_text(sym: dict) -> str:
    """Compact Arabic fact sheet built from computed outputs (daily timeframe only).
    Kept short on purpose: fewer facts = fewer mistakes by a 1.5B model."""
    L = [f"الرمز: {sym['symbol']} ({sym['name']})"]
    ta = sym.get("tf", {}).get("1d", {}).get("technical", {})
    if ta.get("status") == "ok":
        L.append(f"آخر إغلاق يومي: {ta['close']}")
        L.append(f"الاتجاه: {ta['trend']}؛ الموقع من المتوسطات: {ta['ma_position']}")
        L.append(f"RSI14: {ta['rsi14']}؛ وصفه: {rsi_desc(ta['rsi14'])}")
        L.append("أقرب دعم: " + (str(ta["supports"][0]) if ta["supports"] else "لا يوجد قريب"))
        L.append("أقرب مقاومة: " + (str(ta["resistances"][0]) if ta["resistances"] else "لا يوجد قريب"))
    bt = sym.get("backtest", {})
    if bt.get("status") == "ok":
        L.append(f"الاختبار التاريخي اليومي: صفقات {bt['trades']}، رابحة {bt['wins']}، خاسرة {bt['losses']}")
    sig = sym.get("signals", {}).get("1d", 0)
    L.append("إشارة الماسح اليومية الحالية: " + ("شراء" if sig > 0 else "بيع" if sig < 0 else "لا توجد"))
    pl = sym.get("tf", {}).get("1d", {}).get("plan", {})
    if pl.get("status") == "ok":
        L.append(plan_line(pl))
    return "\n".join(L)


def plan_line(pl: dict) -> str:
    side = {"buy": "شراء", "sell": "بيع"}.get(pl.get("side"), "لا صفقة")
    if side == "لا صفقة":
        return "خطة الصفقة الآلية اليومية: لا صفقة"
    tg = pl.get("targets", [])
    far = tg[-1]["price"] if len(tg) > 1 else "غير متوفر"
    return (f"خطة الصفقة الآلية اليومية: {side}؛ الحالة: {pl['status_ar']}؛ الدخول {pl['entry']}؛ الوقف {pl['stop']}؛ "
            f"الهدف القريب {tg[0]['price'] if tg else 'غير متوفر'}؛ الهدف البعيد {far}")


def semantic_guard(text: str, sym: dict) -> list[str]:
    """Reject wording that contradicts the computed facts (trend, MA side, levels, counts, signal)."""
    bad = []
    t = text.translate(AR_DIGITS)
    ta = sym.get("tf", {}).get("1d", {}).get("technical", {})
    if ta.get("status") == "ok":
        trend0 = ta["trend"].split("/")[0]
        for m in re.finditer(r"الاتجاه\s*(?:العام\s*|الحالي\s*)?(?:هو\s*)?:?\s*(صاعد|هابط|عرضي)", t):
            if m.group(1) != trend0:
                bad.append(f"trend {m.group(1)}")
        side = "فوق" if ta["ma_position"].startswith("فوق") else "تحت"
        for m in re.finditer(r"(فوق|تحت)\s*(?:ال)?متوسط", t):
            if m.group(1) != side:
                bad.append(f"ma {m.group(1)}")
        for m in re.finditer(r"دعم[^0-9.]{0,12}(\d+(?:\.\d+)?)", t):
            if not any(abs(float(m.group(1)) - x) < 0.011 for x in ta["supports"]):
                bad.append(f"support {m.group(1)}")
        for m in re.finditer(r"مقاوم[ةه]?[^0-9.]{0,12}(\d+(?:\.\d+)?)", t):
            if not any(abs(float(m.group(1)) - x) < 0.011 for x in ta["resistances"]):
                bad.append(f"resistance {m.group(1)}")
        if re.search(r"زخم\s*(قوي|ضعيف)", t):
            bad.append("momentum adjective")
        desc = rsi_desc(ta["rsi14"])
        for w in ("تشبع بيعي", "تشبع شرائي"):
            if w in t and w not in desc:
                bad.append(w)
    bt = sym.get("backtest", {})
    if bt.get("status") == "ok":
        for m in re.finditer(r"(\d+)\s*(?:صفق[ةه]|صفقات)?\s*رابح", t):
            if int(m.group(1)) != bt["wins"]:
                bad.append("wins")
        for m in re.finditer(r"(\d+)\s*(?:صفق[ةه]|صفقات)?\s*خاسر", t):
            if int(m.group(1)) != bt["losses"]:
                bad.append("losses")
    pl = sym.get("tf", {}).get("1d", {}).get("plan", {})
    if pl.get("status") == "ok":
        pside = {"buy": "شراء", "sell": "بيع"}.get(pl.get("side"))
        for m in re.finditer(r"خط[ةه][^.]{0,30}?(شراء|بيع)", t):
            if m.group(1) != pside:
                bad.append("plan side")
    sig = sym.get("signals", {}).get("1d", 0)
    says_none = bool(re.search(r"لا\s*توجد\s*إشار|لا\s*إشار", t))
    says_buy = bool(re.search(r"إشار[ةه]?[^.]{0,25}شراء", t))
    says_sell = bool(re.search(r"إشار[ةه]?[^.]{0,25}بيع", t))
    if sig == 0 and (says_buy or says_sell):
        bad.append("signal invented")
    if sig != 0 and says_none:
        bad.append("signal missed")
    if sig > 0 and says_sell or sig < 0 and says_buy:
        bad.append("signal side")
    return bad


def template(sym: dict) -> str:
    t = sym.get("tf", {}).get("1d", {}).get("technical", {})
    if t.get("status") != "ok":
        return "لا تتوفر بيانات كافية لملخص في هذا التشغيل."
    parts = [f"{sym['symbol']}: آخر إغلاق يومي {t['close']}، والاتجاه {t['trend']} ({t['ma_position']})."]
    parts.append(f"مؤشر القوة النسبية {t['rsi14']} ووصفه {rsi_desc(t['rsi14'])}.")
    if t["supports"]:
        parts.append(f"أقرب دعم {t['supports'][0]}.")
    if t["resistances"]:
        parts.append(f"أقرب مقاومة {t['resistances'][0]}.")
    sig = sym.get("signals", {}).get("1d", 0)
    parts.append("إشارة الماسح اليومية الحالية: " + ("شراء." if sig > 0 else "بيع." if sig < 0 else "لا توجد."))
    bt = sym.get("backtest", {})
    if bt.get("status") == "ok":
        parts.append(f"الاختبار التاريخي: {bt['trades']} صفقة، {bt['wins']} رابحة و{bt['losses']} خاسرة.")
    pl = t and sym.get("tf", {}).get("1d", {}).get("plan", {})
    if pl and pl.get("status") == "ok":
        parts.append(plan_line(pl) + ".")
    return " ".join(parts)


EXAMPLE_FACTS = ("الرمز: XYZ (Example Corp)\nآخر إغلاق يومي: 41.7\nالاتجاه: هابط؛ الموقع من المتوسطات: تحت المتوسطين 50 و200\n"
                 "RSI14: 33.1؛ وصفه: محايد (بين 30 و70)\nأقرب دعم: 40.05\nأقرب مقاومة: 43.9\n"
                 "الاختبار التاريخي اليومي: صفقات 21، رابحة 9، خاسرة 12\nإشارة الماسح اليومية الحالية: شراء\n"
                 "خطة الصفقة الآلية اليومية: شراء؛ الحالة: نشطة؛ الدخول 41.7؛ الوقف 39.4؛ الهدف القريب 43.9؛ الهدف البعيد 47.2")
EXAMPLE_ANSWER = ("أغلق XYZ آخر مرة عند 41.7، والاتجاه هابط والسعر تحت المتوسطين 50 و200، وأقرب دعم 40.05 وأقرب مقاومة 43.9. "
                  "مؤشر القوة النسبية 33.1 ووصفه محايد. في الاختبار التاريخي اليومي 21 صفقة منها 9 رابحة و12 خاسرة، وإشارة الماسح اليومية الحالية: شراء. "
                  "الخطة الآلية اليومية شراء وحالتها نشطة: الدخول 41.7 والوقف 39.4 والهدف القريب 43.9 والبعيد 47.2.")

SYSTEM = ("أنت مساعد مالي يكتب بالعربية الفصحى المبسطة فقط (بدون أي لغة أخرى). اكتب ملخصاً قصيراً "
          "من 3 إلى 4 جمل فقط اعتماداً على الحقائق المعطاة: الاتجاه وأهم مستوى قريب، ثم الزخم (RSI)، ثم "
          "نتيجة الاختبار التاريخي، ثم خطة الصفقة الآلية (حالتها والدخول والوقف والهدف القريب والبعيد). لا تنقل كل الحقائق. لا تضف أي رقم غير موجود في الحقائق، "
          "ولا تعطِ توصية من عندك ولا تتوقع السعر؛ الخطة الآلية تُنقل كما هي. قل «آخر إغلاق» ولا تقل «اليوم». انقل الأرقام كما هي.")
BAD_SCRIPT = re.compile(r"[\u3040-\u30ff\u3400-\u9fff\uac00-\ud7af\u0400-\u04ff]")


def tidy(text: str, finish: str | None) -> str:
    """Join lines into prose and drop a sentence cut by the token limit.
    A sentence end is . ! ؟ followed by whitespace (a decimal point never is)."""
    text = re.sub(r"\s*\n+\s*", " ", text.strip())
    ends = [m.end() for m in re.finditer(r"[.!؟](?=\s)", text)]
    if finish != "length" and re.search(r"[.!؟]$", text) and not re.search(r"\d\.$", text):
        ends.append(len(text))
    if text and (finish == "length" or not text.endswith((".", "!", "؟"))) and ends:
        text = text[:ends[-1]]
    return text.strip()


def explain(sym: dict, enabled: bool = True) -> dict:
    facts = facts_text(sym)
    if not enabled:
        return {"status": "ok", "text": template(sym), "mode": "template",
                "reason": "النموذج معطّل في الإعدادات", "facts": facts}
    try:
        llm = load()
    except Exception as e:  # noqa: BLE001
        return {"status": "ok", "text": template(sym), "mode": "template",
                "reason": f"تعذّر تحميل النموذج: {str(e)[:120]}", "facts": facts}
    last_bad = []
    for attempt, temp in enumerate((0.2, 0.0)):
        t0 = time.time()
        out = llm.create_chat_completion(
            messages=[{"role": "system", "content": SYSTEM},
                      {"role": "user", "content": "الحقائق:\n" + EXAMPLE_FACTS + "\n\nالملخص:"},
                      {"role": "assistant", "content": EXAMPLE_ANSWER},
                      {"role": "user", "content": "الحقائق:\n" + facts + "\n\nالملخص:"}],
            temperature=temp, max_tokens=330, seed=7)
        ch = out["choices"][0]
        text = tidy(ch["message"]["content"], ch.get("finish_reason"))
        good, bad = guard(text, facts)
        if BAD_SCRIPT.search(text):
            good, bad = False, bad + ["non-Arabic script"]
        sem = semantic_guard(text, sym)
        if sem:
            good, bad = False, bad + sem
        if good and len(text) > 40 and text.endswith((".", "!", "؟")):
            return {"status": "ok", "text": text, "mode": "llm", "model": f"{REPO}/{FILE}",
                    "seconds": round(time.time() - t0, 1), "attempts": attempt + 1, "facts": facts}
        last_bad = bad
    return {"status": "ok", "text": template(sym), "mode": "template",
            "reason": f"رُفض نص النموذج لأنه خالف الحقائق المحسوبة أو كان مقطوعاً: {last_bad[:5]}",
            "facts": facts}
