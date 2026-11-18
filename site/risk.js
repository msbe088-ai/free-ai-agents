// Risk agent: position size / stop calculator. Runs entirely in the browser.
(function () {
  function calcRisk(capital, riskPct, entry, stop, target) {
    capital = Number(capital); riskPct = Number(riskPct); entry = Number(entry); stop = Number(stop);
    if (!(capital > 0) || !(riskPct > 0) || !(entry > 0) || !(stop > 0)) return { error: 'أدخل رأس المال ونسبة المخاطرة والدخول والوقف بأرقام موجبة' };
    if (entry === stop) return { error: 'الدخول يساوي الوقف' };
    const side = stop < entry ? 'شراء' : 'بيع';
    const riskAmount = capital * riskPct / 100;
    const perUnit = Math.abs(entry - stop);
    const unitsExact = riskAmount / perUnit;
    const units = Math.floor(unitsExact);
    const positionValue = units * entry;
    const out = {
      side, riskAmount: round(riskAmount, 2), perUnitRisk: round(perUnit, 6),
      units, unitsExact: round(unitsExact, 6), positionValue: round(positionValue, 2),
      positionValueExact: round(unitsExact * entry, 2),
      pctOfCapital: round(positionValue / capital * 100, 2),
      stopPct: round(perUnit / entry * 100, 2)
    };
    if (target !== undefined && target !== null && target !== '' && Number(target) > 0) {
      const t = Number(target);
      const reward = side === 'شراء' ? t - entry : entry - t;
      out.rr = round(reward / perUnit, 2);
      out.rewardAmount = round(reward * units, 2);
      if (reward <= 0) out.warn = 'الهدف في الاتجاه الخطأ بالنسبة للدخول';
    }
    if (unitsExact * entry > capital) out.leverageWarn = 'قيمة المركز أكبر من رأس المال (تحتاج رافعة) — قلّل المخاطرة أو وسّع الحساب';
    return out;
  }
  function round(x, n) { const p = Math.pow(10, n); return Math.round(x * p) / p; }
  window.calcRisk = calcRisk;
})();
