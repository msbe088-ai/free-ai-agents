# وكلاء الذكاء المجاني 🤖📈

صفحة عربية مجانية ومفتوحة المصدر فيها مجموعة **وكلاء ذكاء اصطناعي**، كل وكيل متخصص في جزء من تحليل الأسهم والكريبتو.
كل شيء يشتغل على **GitHub مجاناً** (GitHub Actions لتشغيل الوكلاء + GitHub Pages لعرض الصفحة) وببيانات مجانية، بدون أي اشتراك مدفوع أو مفتاح API مدفوع.

**الصفحة:** https://msbe088-ai.github.io/free-ai-agents/

> البيانات مجانية وقد تكون **متأخرة**. كل رقم في الصفحة محسوب بالكود من البيانات المجلوبة، ويظهر معه وقت البيانات بتوقيت الرياض. النموذج الصغير يكتب الشرح العربي فقط ولا يخترع أرقاماً (فيه فحص آلي يرفض أي رقم غير موجود في الحقائق). **ليست توصية بيع أو شراء.**

## الوكلاء

| # | الوكيل | الملف | المصدر/الأداة |
|---|---|---|---|
| 1 | البيانات (أسهم) يومي/4 ساعات/ساعة | `agents/data_agent.py` | Yahoo Finance عبر yfinance (4 ساعات مبنية من شموع الساعة) |
| 2 | الكريبتو | `agents/crypto_agent.py` | Binance `data-api.binance.vision` |
| 3 | التحليل الفني (قمم/قيعان، اتجاه، دعوم/مقاومات، RSI، ATR) | `agents/technical_agent.py` | نقاط ارتكاز عامة — ليست طريقتك الخاصة |
| 4 | أنماط الشموع | `agents/patterns_agent.py` | TA-Lib |
| 5 | المستويات/فيبوناتشي عام | `agents/levels_agent.py` | تصحيح عام لآخر موجة كبرى |
| 6 | الأخبار | `agents/news_agent.py` | Yahoo Finance RSS |
| 7 | المشاعر | `agents/sentiment_agent.py` | FinBERT (إنجليزي فقط) |
| 8 | الاقتصاد الكلي | `agents/macro_agent.py` | FRED CSV بدون مفتاح |
| 9 | الأساسيات والأرباح | `agents/fundamentals_agent.py` | SEC EDGAR + موعد الأرباح من ياهو |
| 10 | الخيارات | `agents/options_agent.py` | سلسلة خيارات ياهو (متأخرة) |
| 11 | الاختبار التاريخي | `agents/backtest_agent.py` | backtesting.py — صفقات/رابحة/خاسرة فقط |
| 12 | الماسح | `agents/scanner_agent.py` | نفس قاعدة الاختبار على آخر شمعة مغلقة |
| 13 | حاسبة المخاطرة | `site/risk.js` | تعمل في المتصفح |
| 14 | الشارح العربي | `agents/explainer_agent.py` | Qwen2.5-1.5B-Instruct Q4_K_M (GGUF) عبر llama-cpp-python |
| — | تنبيهات تيليجرام (معطّلة افتراضياً) | `agents/alerts_agent.py` | Telegram Bot API |

صندوق الأسئلة في الصفحة يوجّه سؤالك العربي (بالكلمات المفتاحية) لمخرجات الوكيل المناسب من **آخر تشغيل**. الصفحة ثابتة، فما فيها محادثة مباشرة.

## تعديل قائمة المراقبة

افتح الملف `config/watchlist.yml` في GitHub واضغط ✏️ (Edit):

```yaml
stocks:
  - {symbol: AAPL, name: "Apple", ar: ["ابل", "آبل"]}
crypto:
  - {symbol: BTCUSDT, display: BTC, name: "Bitcoin", news: BTC-USD, ar: ["بيتكوين"]}
```

- **الأسهم:** رمز ياهو (مثل `AAPL`). أضف `etf: true` للصناديق.
- **الكريبتو:** زوج Binance مقابل USDT (مثل `XRPUSDT`)، و`display` الاسم المختصر، و`news` رمز ياهو للأخبار (مثل `XRP-USD`).
- **ar:** أسماء عربية يفهمها صندوق الأسئلة.
- احفظ (Commit). التحديث يظهر في التشغيل القادم، أو شغّله فوراً: **Actions ← Update agents page ← Run workflow**.
- كل رمز يضيف تقريباً 5–10 ثوانٍ لمدة التشغيل.

## الجدولة

- كل 4 ساعات من الاثنين إلى الجمعة (03:23، 07:23، 11:23، 15:23، 19:23، 23:23 بتوقيت الرياض)، ومرتين يومياً في السبت والأحد (06:23 و18:23).
- المستودع عام، فدقائق GitHub Actions على الأجهزة القياسية مجانية.
- **قاعدة الـ60 يوماً:** GitHub يوقف الجدولة في المستودع العام إذا ما صار فيه نشاط 60 يوماً. لذلك فيه وكيل `keepalive.yml` يشتغل أسبوعياً: يعيد تفعيل الجدولة عبر واجهة GitHub الرسمية، وإذا مرّ 45 يوماً بدون أي commit يضيف commit صغير. لو توقفت الجدولة لأي سبب: **Actions ← اختر الـ workflow ← Enable workflow**.

## الأعطال والبيانات القديمة

إذا فشل مصدر (مثلاً ياهو رجّع 429)، الكود يعيد المحاولة مع انتظار متزايد. وإذا استمر الفشل، يعرض **آخر بيانات ناجحة** من التشغيل السابق مع علامة «قديمة» ووقتها الأصلي، فالصفحة ما تنكسر. ما فيه أي بيانات مصطنعة.

## تفعيل تنبيهات تيليجرام (اختياري)

1. في تيليجرام افتح `@BotFather` وأرسل `/newbot` واحفظ **التوكن**.
2. أرسل أي رسالة لبوتك، ثم افتح `https://api.telegram.org/bot<التوكن>/getUpdates` وانسخ رقم `chat.id`.
3. في GitHub: **Settings ← Secrets and variables ← Actions ← New repository secret** وأضف:
   - `TELEGRAM_TOKEN` = التوكن
   - `TELEGRAM_CHAT_ID` = رقم المحادثة
4. من التشغيل القادم يرسل البوت **الإشارات الجديدة فقط** من الماسح. بدون السرّين تبقى التنبيهات معطّلة.

## SEC EDGAR

SEC تطلب بريد تواصل في ترويسة الطلب. البريد محفوظ كسرّ في المستودع باسم `SEC_USER_AGENT` بهذه الصيغة: `FreeAIAgents/1.0 you@example.com`. تقدر تغيّره من نفس صفحة الأسرار.

## التشغيل محلياً

```bash
pip install -r requirements.txt
pip install torch --index-url https://download.pytorch.org/whl/cpu
pip install -r requirements-ml.txt
SEC_USER_AGENT="FreeAIAgents/1.0 you@example.com" python run.py --out site
cd site && python -m http.server 8000
```

## الترخيص

MIT للكود. الشارت: TradingView Lightweight Charts™ (Apache-2.0)، والنسخة محفوظة في `site/vendor/`.
