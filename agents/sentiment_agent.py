"""Sentiment agent: FinBERT (ProsusAI/finbert) on ENGLISH headlines only.
Arabic text was misclassified in feasibility tests, so non-English titles are skipped."""
from __future__ import annotations

from .common import r2

MODEL = "ProsusAI/finbert"
_pipe = None


def _is_english(t: str) -> bool:
    letters = [ch for ch in t if ch.isalpha()]
    return bool(letters) and sum(ch.isascii() for ch in letters) / len(letters) > 0.9


def load():
    global _pipe
    if _pipe is None:
        from transformers import pipeline
        _pipe = pipeline("text-classification", model=MODEL, top_k=None, device=-1)
    return _pipe


def score(news: dict) -> dict:
    if news.get("status") != "ok":
        return {"status": "error", "error": "لا توجد عناوين (فشل وكيل الأخبار)"}
    titles = [x["title"] for x in news["items"]]
    eng = [t for t in titles if _is_english(t)]
    if not eng:
        return {"status": "na", "reason": "لا توجد عناوين إنجليزية"}
    pipe = load()
    out = pipe(eng, truncation=True, max_length=128, batch_size=16)
    per = []
    for t, scores in zip(eng, out):
        best = max(scores, key=lambda s: s["score"])
        per.append({"title": t, "label": best["label"], "score": r2(best["score"], 3)})
    pos = sum(p["label"] == "positive" for p in per)
    neg = sum(p["label"] == "negative" for p in per)
    neu = len(per) - pos - neg
    net = (pos - neg) / len(per)
    overall = "إيجابي" if net > 0.2 else "سلبي" if net < -0.2 else "محايد"
    return {"status": "ok", "model": MODEL, "n": len(per), "positive": pos, "negative": neg,
            "neutral": neu, "net": r2(net, 2), "overall": overall, "items": per,
            "skipped_non_english": len(titles) - len(eng),
            "note": "النموذج إنجليزي فقط؛ يُقيَّم نص العنوان الإنجليزي فقط"}
