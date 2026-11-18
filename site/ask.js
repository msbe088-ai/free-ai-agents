// Question box: client-side Arabic keyword routing to the PRECOMPUTED agent outputs.
(function () {
  function norm(s) {
    return (s || '').toLowerCase()
      .replace(/[\u064B-\u0652\u0640]/g, '')
      .replace(/[أإآٱ]/g, 'ا').replace(/ة/g, 'ه').replace(/ى/g, 'ي')
      .replace(/ؤ/g, 'و').replace(/ئ/g, 'ي').replace(/[؟?!.,،]/g, ' ')
      .replace(/\s+/g, ' ').trim();
  }
  // order matters: first match wins
  const TOPICS = [
    { id: 'risk', tab: 'risk', words: ['مخاطره', 'حجم الصفقه', 'حجم المركز', 'كم سهم', 'كم اشتري', 'كم احط', 'وقف الخساره', 'ستوب', 'لوت'] },
    { id: 'scanner', tab: 'scanner', words: ['اشاره', 'اشارات', 'سكانر', 'الماسح', 'ماسح', 'فرص', 'فرصه'] },
    { id: 'backtest', tab: 'backtest', words: ['باك', 'اختبار تاريخي', 'الاختبار', 'نسبه النجاح', 'كم صفقه', 'صفقات', 'رابحه', 'خاسره', 'ربح وخساره'] },
    { id: 'fib', tab: 'levels', words: ['فيبو', 'فيبوناتشي', 'فايبو', 'تصحيح', 'ارتداد', 'نسب'] },
    { id: 'patterns', tab: 'patterns', words: ['شمعه', 'شموع', 'نمط', 'انماط', 'نموذج', 'دوجي', 'ابتلاع', 'مطرقه', 'هارامي'] },
    { id: 'options', tab: 'options', words: ['اوبشن', 'اوبشنات', 'خيارات', 'عقود', 'كول', 'بوت', 'اوبن انترست', 'تذبذب ضمني'] },
    { id: 'fund', tab: 'fundamentals', words: ['ارباح', 'الارباح', 'ايرادات', 'مبيعات', 'اساسي', 'اساسيات', 'eps', 'صافي الدخل', 'قوائم', 'نتائج'] },
    { id: 'macro', tab: 'macro', words: ['فايده', 'الفايده', 'فوايد', 'تضخم', 'بطاله', 'سندات', 'عايد', 'الفيدرالي', 'الفدرالي', 'اقتصاد', 'cpi'] },
    { id: 'sentiment', tab: 'sentiment', words: ['مشاعر', 'معنويات', 'تفاول', 'تشاوم', 'سنتمنت', 'مزاج'] },
    { id: 'news', tab: 'news', words: ['خبر', 'اخبار', 'الاخبار', 'جديد'] },
    { id: 'technical', tab: 'technical', words: ['دعم', 'مقاومه', 'مقاومات', 'دعوم', 'اتجاه', 'ترند', 'rsi', 'قمه', 'قاع', 'فني', 'متوسط', 'مستويات'] },
    { id: 'crypto', tab: 'crypto', words: ['كريبتو', 'العملات الرقميه', 'العملات المشفره'] },
    { id: 'price', tab: 'data', words: ['سعر', 'كم صار', 'اغلاق', 'وصل', 'كم'] },
    { id: 'summary', tab: 'summary', words: ['ملخص', 'رايك', 'تحليل', 'وضع', 'شرح'] }
  ];
  function findSymbol(q, symbols) {
    const nq = ' ' + norm(q) + ' ';
    for (const s of symbols) {
      const sym = s.symbol.toLowerCase();
      if (new RegExp('(^|[^a-z])' + sym + '([^a-z]|$)').test(nq)) return s.symbol;
    }
    let best = null, bestLen = 0;
    for (const s of symbols) {
      for (const a of (s.ar || [])) {
        const na = norm(a);
        if (na.length >= 2 && nq.includes(na) && na.length > bestLen) { best = s.symbol; bestLen = na.length; }
        // allow attached prefixes like "لابل" / "بابل" / "وابل"
        if (na.length >= 3 && new RegExp('[ ](ل|ب|و|ف|ال)' + na).test(nq) && na.length > bestLen) { best = s.symbol; bestLen = na.length; }
      }
    }
    return best;
  }
  function routeQuestion(q, symbols) {
    const nq = norm(q);
    let topic = null;
    for (const t of TOPICS) { if (t.words.some(w => nq.includes(norm(w)))) { topic = t; break; } }
    if (!topic) topic = TOPICS.find(t => t.id === 'summary');
    return { topic: topic.id, tab: topic.tab, symbol: findSymbol(q, symbols) };
  }
  window.askNorm = norm;
  window.routeQuestion = routeQuestion;
})();
