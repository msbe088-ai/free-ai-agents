// Free AI agents page — renders the static JSON written by the GitHub Actions run.
(function () {
  const TF_AR = { '1d': 'يومي', '4h': '4 ساعات', '1h': 'ساعة' };
  const TABS = [
    ['summary', 'الملخص العربي'], ['plan', 'خطة الصفقة'], ['data', 'البيانات'], ['crypto', 'الكريبتو'], ['technical', 'التحليل الفني'],
    ['patterns', 'أنماط الشموع'], ['levels', 'المستويات/فيبوناتشي'], ['news', 'الأخبار'], ['sentiment', 'المشاعر'],
    ['macro', 'الاقتصاد الكلي'], ['fundamentals', 'الأساسيات والأرباح'], ['options', 'الخيارات'],
    ['backtest', 'الاختبار التاريخي'], ['scanner', 'الماسح'], ['risk', 'حاسبة المخاطرة'], ['status', 'حالة الوكلاء']
  ];
  const state = { index: null, sym: null, data: {}, tf: '1d', tab: 'summary', chart: null, candle: null, vol: null, lines: [], planLines: [] };
  const PLAN_COLORS = { entry: '#4c8dff', stop: '#ff9800', TP1: '#c6ff00', TP2: '#00e5ff', TP3: '#e040fb' };
  const SIDE_AR = { buy: 'شراء', sell: 'بيع', none: 'لا صفقة' };
  const $ = (id) => document.getElementById(id);
  const esc = (s) => String(s == null ? '' : s).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const fmt = (x) => x == null ? '—' : (typeof x === 'number' ? x.toLocaleString('en-US', { maximumFractionDigits: 6 }) : esc(x));
  const pctCls = (x) => x == null ? '' : (x >= 0 ? 'up' : 'down');
  const earnPast = (f) => !!(f.next_earnings && f.next_earnings.length && f.next_earnings[f.next_earnings.length - 1] < new Date().toISOString().slice(0, 10));
  const sideBadge = (s) => `<span class="badge ${s === 'شراء' ? 'b-buy' : 'b-sell'}">${esc(s)}</span>`;

  function badge(sec) {
    if (!sec) return '<span class="badge b-err">لا يوجد</span>';
    if (sec.stale) return `<span class="badge b-stale" title="${esc(sec.stale_reason)}">آخر بيانات ناجحة (قديمة)</span>`;
    if (sec.status === 'ok') return '<span class="badge b-ok">يعمل</span>';
    if (sec.status === 'na') return '<span class="badge">غير متاح</span>';
    return '<span class="badge b-err">فشل</span>';
  }
  function secErr(sec) {
    if (!sec) return '<p class="muted">لا توجد بيانات.</p>';
    if (sec.status === 'na') return `<p class="muted">غير متاح: ${esc(sec.reason)}</p>`;
    if (sec.status !== 'ok') return `<p class="muted">فشل هذا الوكيل في آخر تشغيل: <span class="ltr">${esc(sec.error)}</span></p>`;
    return '';
  }
  function stamp(sec) {
    if (!sec) return '';
    const p = [];
    if (sec.source) p.push('المصدر: ' + esc(sec.source));
    if (sec.data_time_label) p.push('وقت البيانات: ' + esc(sec.data_time_label));
    if (sec.fetched_at_label) p.push('وقت الجلب: ' + esc(sec.fetched_at_label));
    if (sec.stale) p.push('⚠️ ' + esc(sec.stale_reason));
    return `<p class="muted">${p.join(' · ')}</p>`;
  }

  async function getJSON(url) {
    const r = await fetch(url + (url.includes('?') ? '&' : '?') + 'v=' + Date.now(), { cache: 'no-store' });
    if (!r.ok) throw new Error('HTTP ' + r.status + ' ' + url);
    return r.json();
  }
  async function loadSym(s) {
    if (!state.data[s]) state.data[s] = await getJSON('data/sym/' + encodeURIComponent(s) + '.json');
    return state.data[s];
  }

  // ---------- chart ----------
  function initChart() {
    const el = $('chart');
    state.chart = LightweightCharts.createChart(el, {
      autoSize: true,
      layout: { background: { type: 'solid', color: '#121826' }, textColor: '#c9d1d9', fontSize: 12 },
      grid: { vertLines: { color: '#1b2436' }, horzLines: { color: '#1b2436' } },
      rightPriceScale: { borderColor: '#243049' },
      timeScale: { borderColor: '#243049', timeVisible: false, secondsVisible: false },
      crosshair: { mode: 0 }
    });
    state.candle = state.chart.addCandlestickSeries({ upColor: '#26a69a', downColor: '#ef5350', borderVisible: false, wickUpColor: '#26a69a', wickDownColor: '#ef5350' });
    state.vol = state.chart.addHistogramSeries({ priceScaleId: '', priceFormat: { type: 'volume' }, color: '#2a3550' });
    state.vol.priceScale().applyOptions({ scaleMargins: { top: 0.82, bottom: 0 } });
  }
  function drawChart() {
    const d = state.data[state.sym]; if (!d || !d.tf || !d.tf[state.tf]) return;
    const t = d.tf[state.tf];
    state.chart.applyOptions({ timeScale: { timeVisible: state.tf !== '1d' } });
    const bars = t.bars.map(b => ({ time: b[0], open: b[1], high: b[2], low: b[3], close: b[4] }));
    state.candle.setData(bars);
    state.vol.setData(t.bars.map(b => ({ time: b[0], value: b[5] || 0, color: b[4] >= b[1] ? 'rgba(38,166,154,.35)' : 'rgba(239,83,80,.35)' })));
    state.lines.forEach(l => state.candle.removePriceLine(l)); state.lines = []; state.planLines = [];
    const add = (price, color, title, style) => { if (price == null) return; state.lines.push(state.candle.createPriceLine({ price, color, lineWidth: 1, lineStyle: style, axisLabelVisible: true, title })); };
    const ta = t.technical || {};
    if ($('tgLevels').checked && ta.status === 'ok') {
      (ta.supports || []).forEach((p, i) => add(p, '#26a69a', 'دعم ' + (i + 1), 2));
      (ta.resistances || []).forEach((p, i) => add(p, '#ef5350', 'مقاومة ' + (i + 1), 2));
    }
    if ($('tgPlan').checked && t.plan && t.plan.status === 'ok' && t.plan.side !== 'none') {
      const p = t.plan;
      const addP = (price, color, title) => { if (price == null) return; const l = state.candle.createPriceLine({ price, color, lineWidth: 2, lineStyle: 0, axisLabelVisible: true, title }); state.lines.push(l); state.planLines.push(l); };
      addP(p.entry, PLAN_COLORS.entry, 'دخول ' + SIDE_AR[p.side]);
      addP(p.stop, PLAN_COLORS.stop, 'وقف');
      (p.targets || []).slice(0, 3).forEach((tg, k) => addP(tg.price, PLAN_COLORS[tg.name], (k === 0 ? 'هدف قريب ' : 'هدف بعيد ') + tg.name));
    }
    const lv = t.levels || {};
    if ($('tgFib').checked && lv.status === 'ok') lv.levels.forEach(l => add(l.price, '#f0b90b', 'فيبو ' + l.ratio, 1));
    const markers = [];
    const times = new Set(bars.map(b => b.time));
    if ($('tgPatterns').checked && t.patterns && t.patterns.markers) {
      t.patterns.markers.forEach(m => {
        if (!times.has(m.time) || m.idx_from_end > 30) return;
        const doji = m.direction === 'neutral';
        markers.push({ time: m.time, position: m.direction === 'bear' ? 'aboveBar' : 'belowBar', color: m.direction === 'bull' ? '#26a69a' : m.direction === 'bear' ? '#ef5350' : '#8b97ad', shape: m.direction === 'bull' ? 'arrowUp' : m.direction === 'bear' ? 'arrowDown' : 'circle', size: doji ? 0.5 : 1, text: (doji || m.idx_from_end > 10) ? '' : m.name });
      });
    }
    if ($('tgSwings').checked && ta.status === 'ok') {
      (ta.swing_highs || []).forEach(s => times.has(s.time) && markers.push({ time: s.time, position: 'aboveBar', color: '#f0b90b', shape: 'square', text: 'قمة' }));
      (ta.swing_lows || []).forEach(s => times.has(s.time) && markers.push({ time: s.time, position: 'belowBar', color: '#4c8dff', shape: 'square', text: 'قاع' }));
    }
    const sig = (d.signals || {})[state.tf];
    const sigBar = (d.tf_bar || {})[state.tf];
    if (sig && times.has(sigBar)) markers.push({ time: sigBar, position: sig > 0 ? 'belowBar' : 'aboveBar', color: sig > 0 ? '#00e676' : '#ff1744', shape: sig > 0 ? 'arrowUp' : 'arrowDown', text: sig > 0 ? 'إشارة شراء' : 'إشارة بيع' });
    const key = (x) => typeof x === 'string' ? Date.parse(x) / 1000 : x;
    markers.sort((a, b) => key(a.time) - key(b.time));
    state.candle.setMarkers(markers);
    const nb = bars.length;
    state.chart.timeScale().setVisibleLogicalRange({ from: Math.max(0, nb - (window.innerWidth < 700 ? 90 : 160)), to: nb + 4 });
    $('chartTitle').textContent = `${d.symbol} — ${d.name} — ${TF_AR[state.tf]}`;
    $('chartFoot').innerHTML = `${esc(t.source)} · ${esc(t.last_bar_time_label)}${t.last_bar_forming ? ' (الشمعة الأخيرة لم تُغلق بعد؛ التحليل على الشموع المغلقة فقط)' : ''} · وقت الجلب ${esc(t.fetched_at_label)} · ${state.tf === '1d' ? 'المحور بتاريخ السوق' : 'المحور بتوقيت الرياض'}${d.stale ? ' · ⚠️ ' + esc(d.stale_reason) : ''}`;
  }

  // ---------- tabs ----------
  function renderTabs() {
    $('tabs').innerHTML = TABS.map(([id, ar]) => `<button class="tab${state.tab === id ? ' active' : ''}" data-tab="${id}" role="tab">${ar}</button>`).join('');
    $('tabs').querySelectorAll('.tab').forEach(b => b.onclick = () => { state.tab = b.dataset.tab; renderTabs(); renderTab(); });
  }
  function renderTab() { $('tabBody').innerHTML = (R[state.tab] || (() => ''))(); if (state.tab === 'risk') bindRisk(); }

  function planText(p, sym, tfAr) {
    if (!p || p.status !== 'ok') return 'خطة الصفقة غير متاحة.';
    if (p.side === 'none') return `خطة ${sym} (${tfAr}): ${p.status_ar}. ${p.entry_rule || ''}`;
    const tg = p.targets || [];
    return `خطة ${sym} الآلية (${tfAr}): ${SIDE_AR[p.side]} — ${p.status_ar}.\nالدخول ${fmt(p.entry)} · الوقف ${fmt(p.stop)}\n` +
      tg.map((x, k) => `${k === 0 ? 'الهدف القريب' : 'هدف بعيد'} ${x.name}: ${fmt(x.price)} (${fmt(x.r)}R)`).join('\n') +
      `\nالإلغاء: ${p.invalidation}`;
  }
  const R = {
    plan() {
      const d = state.data[state.sym], p = (d.tf[state.tf] || {}).plan;
      if (!p || p.status !== 'ok') return '<h3>خطة الصفقة</h3>' + secErr(p);
      const h = p.history || {};
      const sideCls = p.side === 'buy' ? 'b-buy' : p.side === 'sell' ? 'b-sell' : '';
      const rows = p.side === 'none' ? '' : `<table><tr><th>البند</th><th>السعر</th><th>مضاعف R</th><th>المصدر</th></tr>
        <tr><td><span style="color:${PLAN_COLORS.entry}">■</span> الدخول</td><td><b>${fmt(p.entry)}</b></td><td>—</td><td>${p.basis === 'signal' ? 'إغلاق شمعة الإشارة (التنفيذ عند افتتاح التالية)' : 'مستوى الاختراق'}</td></tr>
        <tr><td><span style="color:${PLAN_COLORS.stop}">■</span> الوقف</td><td><b>${fmt(p.stop)}</b></td><td>−1R</td><td>${esc(p.stop_rule)}</td></tr>
        ${(p.targets || []).map((t, k) => `<tr><td><span style="color:${PLAN_COLORS[t.name]}">■</span> ${k === 0 ? 'الهدف القريب' : 'هدف بعيد'} ${t.name}</td><td><b>${fmt(t.price)}</b></td><td>${fmt(t.r)}R</td><td>${esc(t.source)}</td></tr>`).join('')}</table>`;
      return `<h3>خطة الصفقة الآلية — ${esc(d.symbol)} (${TF_AR[state.tf]}) <span class="badge ${sideCls}">${SIDE_AR[p.side]}</span> ${badge(p)}</h3>
        <div class="kv"><div>الحالة</div><div><b>${esc(p.status_ar)}</b></div>
        <div>شرط الدخول</div><div>${esc(p.entry_rule || '—')}</div>
        ${p.fill != null ? `<div>سعر التنفيذ الفعلي (افتتاح)</div><div>${fmt(p.fill)}</div>` : ''}
        <div>الإلغاء</div><div>${esc(p.invalidation || '—')}</div>
        <div>المخاطرة لكل وحدة</div><div>${fmt(p.risk_per_unit)} (ATR14 = ${fmt(p.atr14)})</div>
        ${p.previous_plan ? `<div>الخطة السابقة</div><div>${SIDE_AR[p.previous_plan.side]} من إشارة ${esc(p.previous_plan.signal_bar)}: ${esc(p.previous_plan.status_ar)}</div>` : ''}</div>
        ${rows}
        <b>فحص تاريخي لنفس القاعدة (${TF_AR[state.tf]})</b>
        <table><tr><th>الصفقات</th><th>الرابحة</th><th>الخاسرة</th></tr><tr><td><b>${h.trades ?? '—'}</b></td><td class="up"><b>${h.wins ?? '—'}</b></td><td class="down"><b>${h.losses ?? '—'}</b></td></tr></table>
        <p class="muted">${esc(h.rule || '')} · الفترة ${esc(h.period_from)} → ${esc(h.period_to)}. صفقة مفتوحة في آخر البيانات لا تُحسب.</p>
        <p class="muted">⚠️ ${esc(p.method)}. محسوبة على الشموع المغلقة فقط. فعّل/أطفئ «خطة الصفقة» فوق الشارت لرسم الخطوط.</p>`;
    },
    summary() {
      const d = state.data[state.sym], s = d.summary || {};
      return `<h3>الملخص العربي — ${esc(d.symbol)} ${badge(s.status ? s : null)}</h3>
        <div class="summary">${esc(s.text || 'لا يوجد ملخص')}</div>
        <p class="muted">${s.mode === 'llm' ? 'كتبه النموذج المحلي الصغير Qwen2.5-1.5B (GGUF) من الأرقام المحسوبة فقط، وتحقق الكود أن كل رقم فيه موجود في الحقائق.' : 'ملخص بقالب ثابت من الأرقام المحسوبة' + (s.reason ? ' — السبب: ' + esc(s.reason) : '')} · أُنشئ ${esc(s.generated_at_label)}</p>
        <details><summary class="muted">الحقائق التي أُعطيت للنموذج</summary><pre style="white-space:pre-wrap">${esc(s.facts || '')}</pre></details>`;
    },
    data() {
      const d = state.data[state.sym], t = d.tf[state.tf];
      const last = t.bars.slice(-6).reverse();
      return `<h3>وكيل البيانات — ${esc(d.symbol)} (${TF_AR[state.tf]}) ${badge(d.tf ? { status: 'ok', stale: d.stale, stale_reason: d.stale_reason } : null)}</h3>
        <div class="kv"><div>المصدر</div><div>${esc(t.source)}</div><div>آخر سعر</div><div>${fmt(t.last_close)}</div>
        <div>آخر شمعة</div><div>${esc(t.last_bar_time_label)} ${t.last_bar_forming ? '(لم تُغلق)' : '(مغلقة)'}</div><div>وقت الجلب</div><div>${esc(t.fetched_at_label)}</div><div>عدد الشموع</div><div>${t.bars.length}</div></div>
        <table><tr><th>الوقت</th><th>افتتاح</th><th>أعلى</th><th>أدنى</th><th>إغلاق</th><th>حجم</th></tr>
        ${last.map(b => `<tr><td class="ltr">${typeof b[0] === 'string' ? b[0] : new Date((b[0] - 0) * 1000).toISOString().slice(0, 16).replace('T', ' ')}</td><td>${fmt(b[1])}</td><td>${fmt(b[2])}</td><td>${fmt(b[3])}</td><td>${fmt(b[4])}</td><td>${fmt(b[5])}</td></tr>`).join('')}</table>
        <p class="muted">${d.kind === 'crypto' ? 'الكريبتو من Binance (فريم 4 ساعات أصلي).' : 'فريم 4 ساعات مبني من شموع الساعة في ياهو (09:30–13:30 و13:30–16:00 بتوقيت نيويورك).'} الأوقات في الجدول بتوقيت الرياض للفريمات اللحظية.</p>`;
    },
    crypto() {
      const c = state.index.crypto24 || {};
      if (c.status !== 'ok') return '<h3>وكيل الكريبتو</h3>' + secErr(c);
      return `<h3>وكيل الكريبتو ${badge(c)}</h3><table><tr><th>الزوج</th><th>آخر سعر</th><th>تغير 24س %</th><th>أعلى 24س</th><th>أدنى 24س</th></tr>
        ${Object.entries(c.items).map(([k, v]) => `<tr><td>${esc(k)}</td><td>${fmt(v.last)}</td><td class="${pctCls(v.change_pct_24h)}">${fmt(v.change_pct_24h)}</td><td>${fmt(v.high_24h)}</td><td>${fmt(v.low_24h)}</td></tr>`).join('')}</table>
        <p class="muted">المصدر: ${esc(c.source)} · وقت الجلب: ${esc(c.fetched_at_label)}</p>`;
    },
    technical() {
      const d = state.data[state.sym], t = d.tf[state.tf].technical;
      if (!t || t.status !== 'ok') return '<h3>التحليل الفني</h3>' + secErr(t);
      return `<h3>التحليل الفني — ${TF_AR[state.tf]} ${badge(t)}</h3>
        <div class="kv"><div>آخر إغلاق مغلق</div><div>${fmt(t.close)}</div><div>الاتجاه</div><div><b>${esc(t.trend)}</b></div>
        <div>الهيكل</div><div>${esc(t.structure)}</div><div>المتوسطات</div><div>${esc(t.ma_position)} (20: ${fmt(t.sma20)} · 50: ${fmt(t.sma50)} · 200: ${fmt(t.sma200)})</div>
        <div>RSI 14</div><div>${fmt(t.rsi14)}</div><div>ATR 14</div><div>${fmt(t.atr14)}</div>
        <div>الدعوم</div><div class="up">${t.supports.length ? t.supports.map(fmt).join(' · ') : 'لا يوجد دعم قريب ضمن آخر 250 شمعة'}</div>
        <div>المقاومات</div><div class="down">${t.resistances.length ? t.resistances.map(fmt).join(' · ') : 'لا توجد مقاومة قريبة ضمن آخر 250 شمعة'}</div></div>
        <p class="muted">${esc(t.method)}</p>${stamp(t)}`;
    },
    patterns() {
      const p = state.data[state.sym].tf[state.tf].patterns;
      if (!p || p.status !== 'ok') return '<h3>أنماط الشموع</h3>' + secErr(p);
      const dir = (x) => x === 'bull' ? '<span class="up">صاعد</span>' : x === 'bear' ? '<span class="down">هابط</span>' : 'محايد';
      return `<h3>أنماط الشموع — آخر ${p.window_bars} شموع مغلقة (${TF_AR[state.tf]}) ${badge(p)}</h3>
        ${p.recent.length ? `<table><tr><th>النمط</th><th>الاتجاه</th><th>قبل كم شمعة</th></tr>${p.recent.map(x => `<tr><td>${esc(x.name)} <span class="muted ltr">${esc(x.code)}</span></td><td>${dir(x.direction)}</td><td>${x.idx_from_end}</td></tr>`).join('')}</table>` : '<p>لا توجد أنماط ضمن القائمة في آخر الشموع.</p>'}
        <p class="muted">المكتبة: ${esc(p.library)} · صاعد ${p.counts_recent.bull} · هابط ${p.counts_recent.bear} · محايد ${p.counts_recent.neutral}. الأنماط مرسومة على الشارت (آخر 60 شمعة).</p>`;
    },
    levels() {
      const l = state.data[state.sym].tf[state.tf].levels;
      if (!l || l.status !== 'ok') return '<h3>المستويات</h3>' + secErr(l);
      return `<h3>فيبوناتشي عام — ${TF_AR[state.tf]} ${badge(l)}</h3>
        <div class="kv"><div>الموجة</div><div>${esc(l.swing)}</div><div>القمة</div><div>${fmt(l.swing_high.price)}</div><div>القاع</div><div>${fmt(l.swing_low.price)}</div>
        <div>أقرب مستوى تحت السعر</div><div>${l.nearest_below ? fmt(l.nearest_below.price) + ' (' + l.nearest_below.ratio + ')' : '—'}</div>
        <div>أقرب مستوى فوق السعر</div><div>${l.nearest_above ? fmt(l.nearest_above.price) + ' (' + l.nearest_above.ratio + ')' : '—'}</div></div>
        <table><tr><th>النسبة</th><th>السعر</th></tr>${l.levels.map(x => `<tr><td>${x.ratio}</td><td>${fmt(x.price)}</td></tr>`).join('')}</table>
        <p class="muted">${esc(l.method)}. فعّل «فيبوناتشي عام» فوق الشارت لرسمها.</p>`;
    },
    news() {
      const n = state.data[state.sym].news;
      if (!n || n.status !== 'ok') return '<h3>الأخبار</h3>' + secErr(n);
      return `<h3>وكيل الأخبار ${badge(n)}</h3><ul class="news">${n.items.map(x => `<li><a href="${esc(x.link)}" target="_blank" rel="noopener" dir="ltr">${esc(x.title)}</a> <span class="muted">${esc(x.published_label || '')}</span></li>`).join('')}</ul>${stamp(n)}`;
    },
    sentiment() {
      const s = state.data[state.sym].sentiment;
      if (!s || s.status !== 'ok') return '<h3>المشاعر</h3>' + secErr(s);
      return `<h3>وكيل المشاعر (FinBERT) ${badge(s)}</h3>
        <div class="kv"><div>المحصلة</div><div><b>${esc(s.overall)}</b> (صافي ${fmt(s.net)})</div><div>إيجابي / سلبي / محايد</div><div>${s.positive} / ${s.negative} / ${s.neutral} من ${s.n}</div></div>
        <table><tr><th>العنوان</th><th>التصنيف</th><th>الثقة</th></tr>${s.items.map(x => `<tr><td dir="ltr" style="text-align:left">${esc(x.title)}</td><td class="${x.label === 'positive' ? 'up' : x.label === 'negative' ? 'down' : ''}">${x.label === 'positive' ? 'إيجابي' : x.label === 'negative' ? 'سلبي' : 'محايد'}</td><td>${fmt(x.score)}</td></tr>`).join('')}</table>
        <p class="muted">النموذج ${esc(s.model)} إنجليزي فقط، لذلك نقيّم العناوين الإنجليزية فقط (العربي كان يُصنَّف خطأً في الاختبار). عناوين غير إنجليزية تُركت: ${s.skipped_non_english}.</p>`;
    },
    macro() {
      const m = state.index.macro;
      if (!m || m.status !== 'ok') return '<h3>الاقتصاد الكلي</h3>' + secErr(m);
      return `<h3>وكيل الاقتصاد الكلي (FRED) ${badge(m)}</h3><table><tr><th>المؤشر</th><th>آخر قيمة</th><th>تاريخها</th><th>السابقة</th></tr>
        ${m.items.map(x => `<tr><td>${esc(x.name)} <span class="muted ltr">${esc(x.id)}</span></td><td><b>${fmt(x.value)}${esc(x.unit)}</b></td><td class="ltr">${esc(x.date)}</td><td>${fmt(x.prev)}${esc(x.unit)} <span class="muted ltr">${esc(x.prev_date)}</span></td></tr>`).join('')}</table>
        ${m.spread_10y_2y != null ? `<p>فرق عائد 10 سنوات − سنتين: <b>${fmt(m.spread_10y_2y)}</b> نقطة مئوية</p>` : ''}
        <p class="muted">${esc(m.note)}. التضخم محسوب سنوياً من مؤشر CPIAUCSL.</p>${stamp(m)}`;
    },
    fundamentals() {
      const f = state.data[state.sym].fundamentals;
      if (!f || f.status !== 'ok') return '<h3>الأساسيات والأرباح</h3>' + secErr(f);
      const rows = (a, unit) => a.map(x => `<tr><td class="ltr">${esc(x.end)}</td><td>${fmt(x.value)} ${unit}</td><td>${esc(x.form)}</td><td class="ltr">${esc(x.filed)}</td></tr>`).join('');
      const head = '<tr><th>نهاية الربع</th><th>القيمة</th><th>النموذج</th><th>تاريخ الإيداع</th></tr>';
      return `<h3>الأساسيات — ${esc(f.entity)} ${badge(f)}</h3>
        <div class="kv"><div>موعد الأرباح القادم (ياهو)</div><div><span class="ltr">${f.next_earnings ? f.next_earnings.map(esc).join(' / ') : '—'}</span>${earnPast(f) ? ' <span class="muted">(تاريخ ماضٍ: ياهو لم يحدّث الموعد القادم بعد)</span>' : ''}</div><div>متوسط تقدير EPS</div><div>${fmt(f.eps_estimate_avg)}</div></div>
        <b>الإيرادات (مليار $)</b><table>${head}${rows(f.revenue_bn, '')}</table>
        <b>صافي الدخل (مليار $)</b><table>${head}${rows(f.net_income_bn, '')}</table>
        <b>ربحية السهم المخففة ($)</b><table>${head}${rows(f.eps_diluted, '')}</table>
        <p class="muted">${esc(f.note)}</p>${stamp(f)}`;
    },
    options() {
      const o = state.data[state.sym].options;
      if (!o || o.status !== 'ok') return '<h3>الخيارات</h3>' + secErr(o);
      return `<h3>وكيل الخيارات — أقرب انتهاء ${esc(o.expiry)} ${badge(o)}</h3>
        <div class="kv"><div>حجم الكول / البوت</div><div>${fmt(o.calls_volume)} / ${fmt(o.puts_volume)}</div>
        <div>العقود المفتوحة كول / بوت</div><div>${fmt(o.calls_oi)} / ${fmt(o.puts_oi)}</div>
        <div>نسبة بوت/كول (الحجم)</div><div>${fmt(o.pc_ratio_volume)}</div><div>نسبة بوت/كول (العقود المفتوحة)</div><div>${fmt(o.pc_ratio_oi)}</div>
        <div>التذبذب الضمني عند السعر (كول/بوت)</div><div>${fmt(o.atm_iv_call_pct)}% / ${fmt(o.atm_iv_put_pct)}%</div>
        <div>أعلى عقود مفتوحة كول</div><div>${o.top_call_oi.map(x => fmt(x.strike) + ' (' + fmt(x.oi) + ')').join(' · ')}</div>
        <div>أعلى عقود مفتوحة بوت</div><div>${o.top_put_oi.map(x => fmt(x.strike) + ' (' + fmt(x.oi) + ')').join(' · ')}</div></div>
        <p class="muted">بيانات ياهو المجانية متأخرة وقد تكون ناقصة؛ ليست تغذية وسيط.</p>${stamp(o)}`;
    },
    backtest() {
      const b = state.data[state.sym].backtest;
      if (!b || b.status !== 'ok') return '<h3>الاختبار التاريخي</h3>' + secErr(b);
      return `<h3>وكيل الاختبار التاريخي ${badge(b)}</h3>
        <table><tr><th>الصفقات</th><th>الرابحة</th><th>الخاسرة</th></tr><tr><td><b>${b.trades}</b></td><td class="up"><b>${b.wins}</b></td><td class="down"><b>${b.losses}</b></td></tr></table>
        <div class="kv"><div>الفترة</div><div class="ltr">${esc(b.period_from)} → ${esc(b.period_to)}</div><div>الفريم</div><div>${esc(b.timeframe)}</div><div>القاعدة</div><div>${esc(b.rule)}</div></div>
        <p class="muted">الرابحة = وصلت الهدف الأول قبل الوقف. الخاسرة = ضربت الوقف أولاً. المكتبة: ${esc(b.library)}. ${esc(b.note)}</p>`;
    },
    scanner() {
      const s = state.index.scanner;
      if (!s) return '<h3>الماسح</h3><p class="muted">لا توجد بيانات.</p>';
      return `<h3>وكيل الماسح ${badge(s)}</h3>
        ${s.signals.length ? `<table><tr><th>الرمز</th><th>الإشارة</th><th>الفريم</th><th>إغلاق شمعة الإشارة</th><th>الشمعة</th></tr>${s.signals.map(x => `<tr><td><a href="#" data-sym="${esc(x.symbol)}" class="symlink">${esc(x.symbol)}</a></td><td>${sideBadge(x.side)}</td><td>${TF_AR[x.tf]}</td><td>${fmt(x.close)}</td><td class="ltr">${typeof x.bar_time === 'string' ? esc(x.bar_time) : new Date((x.bar_time) * 1000).toISOString().slice(0, 16).replace('T', ' ')}</td></tr>`).join('')}</table>` : '<p>لا توجد إشارة حالية في قائمة المراقبة.</p>'}
        <p class="muted">فُحص ${s.scanned} رمزاً. ${esc(s.rule)}. آخر تشغيل: ${esc(state.index.generated_at_label)}. ليست توصية.</p>`;
    },
    risk() {
      const d = state.data[state.sym];
      const ta = (d.tf[state.tf] || {}).technical || {};
      const pl = (d.tf[state.tf] || {}).plan || {};
      const usePlan = pl.status === 'ok' && pl.side !== 'none';
      const e0 = usePlan ? pl.entry : d.last;
      const s0 = usePlan ? pl.stop : (ta.supports || []).find(x => x < d.last);
      const t0 = usePlan ? (pl.targets[0] || {}).price : (ta.resistances || []).find(x => x > d.last);
      return `<h3>حاسبة المخاطرة (تعمل في متصفحك)</h3>
        <div class="risk-grid">
          <label>رأس المال $<input type="number" id="rkCap" value="10000" step="any"></label>
          <label>نسبة المخاطرة %<input type="number" id="rkPct" value="1" step="any"></label>
          <label>سعر الدخول<input type="number" id="rkEntry" value="${e0 ?? ''}" step="any"></label>
          <label>وقف الخسارة<input type="number" id="rkStop" value="${s0 ?? ''}" step="any"></label>
          <label>الهدف (اختياري)<input type="number" id="rkTarget" value="${t0 ?? ''}" step="any"></label>
          <label>&nbsp;<button class="btn" id="rkBtn" type="button">احسب</button></label>
        </div>
        <div class="risk-out" id="rkOut"></div>
        <p class="muted">القيم المبدئية: ${usePlan ? 'دخول ووقف والهدف القريب من خطة الصفقة الآلية' : 'آخر سعر وأقرب دعم/مقاومة من التحليل الفني'} — غيّرها كما تريد. الحساب: مبلغ المخاطرة = رأس المال × النسبة، والكمية = مبلغ المخاطرة ÷ المسافة بين الدخول والوقف.</p>`;
    },
    status() {
      const i = state.index, a = i.agent_status || {};
      const names = { data: 'البيانات (أسهم)', crypto: 'الكريبتو', technical: 'التحليل الفني', patterns: 'أنماط الشموع', levels: 'المستويات', news: 'الأخبار', sentiment: 'المشاعر', fundamentals: 'الأساسيات', options: 'الخيارات', backtest: 'الاختبار التاريخي' };
      return `<h3>حالة الوكلاء في آخر تشغيل</h3>
        <div class="kv"><div>بداية التشغيل</div><div>${esc(i.run_started_label)}</div><div>نهاية التشغيل</div><div>${esc(i.generated_at_label)}</div><div>مدة سكربت الوكلاء</div><div>${fmt(i.run_seconds)} ثانية</div>
        <div>الاقتصاد الكلي</div><div>${badge(i.macro)}</div><div>الماسح</div><div>${badge(i.scanner)}</div>
        <div>تنبيهات تيليجرام</div><div>${i.alerts && i.alerts.status === 'disabled' ? 'معطّلة (لم تُضف الأسرار)' : esc(JSON.stringify(i.alerts))}</div>
        <div>الملخص العربي</div><div>نموذج: ${a.explainer ? a.explainer.llm : 0} · قالب: ${a.explainer ? a.explainer.template : 0}</div></div>
        <table><tr><th>الوكيل</th><th>يعمل</th><th>فشل</th><th>قديم</th><th>غير متاح</th></tr>
        ${Object.entries(names).map(([k, ar]) => { const s = a[k] || {}; return `<tr><td>${ar}</td><td class="up">${s.ok ?? 0}</td><td class="down">${s.error ?? 0}</td><td>${s.stale ?? 0}</td><td>${s.na ?? 0}</td></tr>`; }).join('')}</table>
        ${i.run_url ? `<p><a href="${esc(i.run_url)}" target="_blank" rel="noopener">سجل التشغيل في GitHub Actions</a></p>` : ''}`;
    }
  };

  function riskHTML(r) {
    if (r.error) return `<p class="down">${esc(r.error)}</p>`;
    return `<table><tr><th>البند</th><th>النتيجة</th></tr>
      <tr><td>الاتجاه</td><td>${sideBadge(r.side)}</td></tr>
      <tr><td>مبلغ المخاطرة</td><td id="rkRiskAmt"><b>${fmt(r.riskAmount)}</b> $</td></tr>
      <tr><td>المخاطرة لكل وحدة</td><td>${fmt(r.perUnitRisk)} (${fmt(r.stopPct)}%)</td></tr>
      <tr><td>الكمية (أسهم كاملة)</td><td id="rkUnits"><b>${fmt(r.units)}</b></td></tr>
      <tr><td>الكمية الدقيقة (للكريبتو)</td><td>${fmt(r.unitsExact)}</td></tr>
      <tr><td>قيمة المركز</td><td id="rkValue">${fmt(r.positionValue)} $ (${fmt(r.pctOfCapital)}% من رأس المال)</td></tr>
      ${r.rr != null ? `<tr><td>العائد إلى المخاطرة</td><td>${fmt(r.rr)} : 1 (ربح متوقع عند الهدف ${fmt(r.rewardAmount)} $)</td></tr>` : ''}
      </table>${r.warn ? `<p class="down">${esc(r.warn)}</p>` : ''}${r.leverageWarn ? `<p class="down">${esc(r.leverageWarn)}</p>` : ''}`;
  }
  function bindRisk() {
    const go = () => { $('rkOut').innerHTML = riskHTML(window.calcRisk($('rkCap').value, $('rkPct').value, $('rkEntry').value, $('rkStop').value, $('rkTarget').value)); };
    $('rkBtn').onclick = go; ['rkCap', 'rkPct', 'rkEntry', 'rkStop', 'rkTarget'].forEach(id => $(id).oninput = go); go();
  }

  // ---------- question box ----------
  async function answer(q) {
    const route = window.routeQuestion(q, state.index.symbols);
    const symChanged = route.symbol && route.symbol !== state.sym;
    const target = route.symbol || state.sym;
    await loadSym(target);
    if (symChanged) { state.sym = target; $('symbolSelect').value = target; }
    const d = state.data[target], t = d.tf['1d'], ta = t.technical || {}, run = state.index.generated_at_label;
    let txt = '';
    const okSec = (s) => s && s.status === 'ok';
    switch (route.topic) {
      case 'plan': txt = planText((d.tf[state.tf] || t).plan, d.symbol, TF_AR[state.tf]); break;
      case 'risk': txt = `افتح حاسبة المخاطرة تحت: أدخل رأس المال ونسبة المخاطرة والدخول والوقف. القيم المبدئية لـ ${d.symbol}: الدخول ${fmt(d.last)} والوقف عند أقرب دعم تحت السعر ${fmt((ta.supports || []).find(x => x < d.last))}.`; break;
      case 'scanner': { const s = state.index.scanner.signals; txt = s.length ? 'الإشارات الحالية:\n' + s.map(x => `• ${x.symbol}: ${x.side} على فريم ${TF_AR[x.tf]} (إغلاق ${fmt(x.close)})`).join('\n') : 'لا توجد إشارة حالية في قائمة المراقبة.'; break; }
      case 'backtest': { const b = d.backtest; txt = okSec(b) ? `الاختبار التاريخي لـ ${d.symbol} (يومي، ${b.period_from} → ${b.period_to}): ${b.trades} صفقة، ${b.wins} رابحة و${b.losses} خاسرة.` : 'الاختبار التاريخي غير متاح لهذا الرمز.'; break; }
      case 'fib': { const l = t.levels; txt = okSec(l) ? `فيبوناتشي عام لـ ${d.symbol} (يومي، موجة ${l.swing} من ${fmt(l.swing_low.price)} إلى ${fmt(l.swing_high.price)}):\n` + l.levels.map(x => `${x.ratio} ← ${fmt(x.price)}`).join('\n') : 'المستويات غير متاحة.'; break; }
      case 'patterns': { const p = t.patterns; txt = okSec(p) ? (p.recent.length ? `أنماط الشموع اليومية الحديثة لـ ${d.symbol}: ` + p.recent.map(x => `${x.name} (${x.direction === 'bull' ? 'صاعد' : x.direction === 'bear' ? 'هابط' : 'محايد'}، قبل ${x.idx_from_end} شمعة)`).join('، ') : `لا توجد أنماط في آخر ${p.window_bars} شموع يومية لـ ${d.symbol}.`) : 'غير متاح.'; break; }
      case 'options': { const o = d.options; txt = okSec(o) ? `خيارات ${d.symbol} (انتهاء ${o.expiry}): نسبة بوت/كول بالحجم ${fmt(o.pc_ratio_volume)} وبالعقود المفتوحة ${fmt(o.pc_ratio_oi)}، أعلى عقود كول عند ${fmt(o.top_call_oi[0] && o.top_call_oi[0].strike)} وبوت عند ${fmt(o.top_put_oi[0] && o.top_put_oi[0].strike)}.` : `الخيارات غير متاحة لـ ${d.symbol}: ${esc((o && (o.reason || o.error)) || '')}`; break; }
      case 'fund': { const f = d.fundamentals; if (okSec(f)) { const r = f.revenue_bn.slice(-1)[0], e = f.eps_diluted.slice(-1)[0]; txt = `${f.entity}: آخر ربع مُفصح (${r ? r.end : '—'}) إيرادات ${fmt(r && r.value)} مليار $، وربحية السهم المخففة ${fmt(e && e.value)} $. موعد الأرباح القادم: ${f.next_earnings ? f.next_earnings.join(' / ') + (earnPast(f) ? ' (تاريخ ماضٍ؛ ياهو لم يحدّثه بعد)' : '') : 'غير متوفر'}.`; } else txt = `الأساسيات غير متاحة لـ ${d.symbol}: ${esc((f && (f.reason || f.error)) || '')}`; break; }
      case 'macro': { const m = state.index.macro; txt = okSec(m) ? m.items.map(x => `• ${x.name}: ${fmt(x.value)}${x.unit} (${x.date})`).join('\n') : 'بيانات الاقتصاد غير متاحة.'; break; }
      case 'sentiment': { const s = d.sentiment; txt = okSec(s) ? `مشاعر عناوين ${d.symbol} الإنجليزية: ${s.overall} — إيجابي ${s.positive}، سلبي ${s.negative}، محايد ${s.neutral} من ${s.n}.` : 'المشاعر غير متاحة.'; break; }
      case 'news': { const n = d.news; txt = okSec(n) ? `آخر عناوين ${d.symbol}:\n` + n.items.slice(0, 5).map(x => '• ' + x.title).join('\n') : 'الأخبار غير متاحة.'; break; }
      case 'technical': txt = okSec(ta) ? `${d.symbol} يومي: الاتجاه ${ta.trend}، RSI ${fmt(ta.rsi14)}. الدعوم: ${ta.supports.length ? ta.supports.map(fmt).join('، ') : 'لا يوجد قريب'}. المقاومات: ${ta.resistances.length ? ta.resistances.map(fmt).join('، ') : 'لا يوجد قريب'}.` : 'التحليل الفني غير متاح.'; break;
      case 'crypto': { const c = state.index.crypto24; txt = okSec(c) ? Object.entries(c.items).map(([k, v]) => `• ${k}: ${fmt(v.last)} (${fmt(v.change_pct_24h)}% خلال 24 ساعة)`).join('\n') : 'غير متاح.'; break; }
      case 'price': txt = `آخر سعر لـ ${d.symbol}: ${fmt(d.last)} (التغير اليومي ${fmt(d.change_pct)}%) — ${t.last_bar_time_label}.`; break;
      default: txt = (d.summary && d.summary.text) || 'لا يوجد ملخص.';
    }
    state.tab = route.tab; renderTabs();
    if (symChanged) { drawChart(); renderQuote(); }
    renderTab();
    const tabAr = (TABS.find(x => x[0] === route.tab) || [, ''])[1];
    $('askAnswer').innerHTML = `${esc(txt)}\n<span class="route">الوكيل: ${esc(tabAr)} · الرمز: ${esc(target)}${route.symbol ? '' : ' (الرمز المختار حالياً)'} · الإجابة من آخر تشغيل ${esc(run)}</span>`;
    $('askAnswer').dataset.topic = route.topic; $('askAnswer').dataset.symbol = target;
    return { route, txt };
  }

  function renderQuote() {
    const d = state.data[state.sym];
    $('quote').innerHTML = `<span dir="ltr">${esc(d.symbol)}</span><span class="px">${fmt(d.last)}</span><span dir="ltr" class="${pctCls(d.change_pct)}">${d.change_pct >= 0 ? '+' : ''}${fmt(d.change_pct)}%</span>`;
  }
  async function selectSym(s) {
    state.sym = s; await loadSym(s); renderQuote(); drawChart(); renderTab();
  }

  async function main() {
    try {
      state.index = await getJSON('data/index.json');
    } catch (e) {
      $('notice').textContent = 'تعذّر تحميل بيانات آخر تشغيل: ' + e.message; return;
    }
    const i = state.index;
    const ageH = (Date.now() - Date.parse(i.generated_at)) / 3600000;
    const staleNote = ageH > 13 ? ` · <b class="down">⚠️ آخر تشغيل قبل ${Math.floor(ageH)} ساعة، أقدم من الجدول المعتاد</b>` : '';
    $('notice').innerHTML = `آخر تشغيل للوكلاء: <b>${esc(i.generated_at_label)}</b>${staleNote} · البيانات مجانية وقد تتأخر (ياهو عادة ~15 دقيقة أو أكثر، والشموع اليومية بعد الإغلاق) · ${esc(i.disclaimer)}`;
    $('symbolSelect').innerHTML = `<optgroup label="أسهم وصناديق">${i.symbols.filter(s => s.kind === 'stock').map(s => `<option value="${esc(s.symbol)}">${esc(s.symbol)} — ${esc(s.name)}</option>`).join('')}</optgroup><optgroup label="كريبتو">${i.symbols.filter(s => s.kind === 'crypto').map(s => `<option value="${esc(s.symbol)}">${esc(s.symbol)} — ${esc(s.name)}</option>`).join('')}</optgroup>`;
    const hash = decodeURIComponent((location.hash || '').slice(1)).toUpperCase();
    const first = i.symbols.find(s => s.symbol === hash) ? hash : i.symbols[0].symbol;
    $('symbolSelect').value = first;
    initChart(); renderTabs();
    await selectSym(first);
    $('symbolSelect').onchange = (e) => { location.hash = e.target.value; selectSym(e.target.value); };
    document.querySelectorAll('.tf').forEach(b => b.onclick = () => {
      document.querySelectorAll('.tf').forEach(x => x.classList.remove('active')); b.classList.add('active');
      state.tf = b.dataset.tf; drawChart(); renderTab();
    });
    ['tgPlan', 'tgLevels', 'tgFib', 'tgPatterns', 'tgSwings'].forEach(id => $(id).onchange = drawChart);
    $('tabBody').addEventListener('click', (e) => { const a = e.target.closest('.symlink'); if (a) { e.preventDefault(); $('symbolSelect').value = a.dataset.sym; selectSym(a.dataset.sym); } });
    $('askForm').onsubmit = (e) => { e.preventDefault(); const q = $('askInput').value.trim(); if (q) answer(q); };
    window.__app = { state, answer, selectSym, ready: true };
    document.body.dataset.ready = '1';
  }
  main();
})();
