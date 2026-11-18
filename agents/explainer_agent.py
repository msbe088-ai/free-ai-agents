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


def facts_text(sym: dict) -> str:
    """Compact Arabic fact sheet built from computed outputs (daily timeframe)."""
    L = [f"الرمز: {sym['symbol']} ({sym['name']})"]
    t = sym.get("tf", {}).get("1d", {})
    ta = t.get("technical", {})
    if ta.get("status") == "ok":
        L.append(f"آخر إغلاق يومي: {ta['close']}")
        L.append(f"الاتجاه: {ta['trend']}؛ الهيكل: {ta['structure']}؛ الموقع من المتوسطات: {ta['ma_position']}")
        L.append(f"RSI14: {ta['rsi14']}؛ ATR14: {ta['atr14']}")
        if ta["supports"]:
            L.append("أقرب دعوم: " + "، ".join(str(x) for x in ta["supports"]))
        if ta["resistances"]:
            L.append("أقرب مقاومات: " + "، ".join(str(x) for x in ta["resistances"]))
    pa = t.get("patterns", {})
    if pa.get("status") == "ok" and pa.get("recent"):
        L.append("أنماط شموع حديثة: " + "، ".join(f"{p['name']} ({'صاعد' if p['direction']=='bull' else 'هابط' if p['direction']=='bear' else 'محايد'})" for p in pa["recent"][:4]))
    se = sym.get("sentiment", {})
    if se.get("status") == "ok":
        L.append(f"مشاعر العناوين الإنجليزية: {se['overall']} (إيجابي {se['positive']}، سلبي {se['negative']}، محايد {se['neutral']})")
    bt = sym.get("backtest", {})
    if bt.get("status") == "ok":
        L.append(f"الاختبار التاريخي اليومي: صفقات {bt['trades']}، رابحة {bt['wins']}، خاسرة {bt['losses']}")
    sig = sym.get("signals", {}).get("1d", 0)
    L.append("إشارة الماسح اليومية الحالية: " + ("شراء" if sig > 0 else "بيع" if sig < 0 else "لا توجد"))
    return "\n".join(L)


def template(sym: dict) -> str:
    t = sym.get("tf", {}).get("1d", {}).get("technical", {})
    if t.get("status") != "ok":
        return "لا تتوفر بيانات كافية لملخص في هذا التشغيل."
    parts = [f"{sym['symbol']}: آخر إغلاق يومي {t['close']}، والاتجاه {t['trend']} ({t['ma_position']})."]
    parts.append(f"مؤشر القوة النسبية {t['rsi14']}.")
    if t["supports"]:
        parts.append(f"أقرب دعم {t['supports'][0]}.")
    if t["resistances"]:
        parts.append(f"أقرب مقاومة {t['resistances'][0]}.")
    bt = sym.get("backtest", {})
    if bt.get("status") == "ok":
        parts.append(f"الاختبار التاريخي: {bt['trades']} صفقة، {bt['wins']} رابحة و{bt['losses']} خاسرة.")
    return " ".join(parts)


SYSTEM = ("أنت مساعد مالي يكتب بالعربية الفصحى المبسطة. اكتب ملخصاً قصيراً من 3 إلى 4 جمل "
          "اعتماداً فقط على الحقائق المعطاة. لا تضف أي رقم غير موجود في الحقائق، ولا تعطِ توصية "
          "شراء أو بيع، ولا تتوقع السعر. انقل الأرقام كما هي.")


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
                      {"role": "user", "content": "الحقائق:\n" + facts + "\n\nالملخص:"}],
            temperature=temp, max_tokens=220, seed=7)
        text = out["choices"][0]["message"]["content"].strip()
        good, bad = guard(text, facts)
        if good and len(text) > 20:
            return {"status": "ok", "text": text, "mode": "llm", "model": f"{REPO}/{FILE}",
                    "seconds": round(time.time() - t0, 1), "attempts": attempt + 1, "facts": facts}
        last_bad = bad
    return {"status": "ok", "text": template(sym), "mode": "template",
            "reason": f"رُفض نص النموذج لأنه ذكر أرقاماً غير موجودة في الحقائق: {last_bad[:5]}",
            "facts": facts}
