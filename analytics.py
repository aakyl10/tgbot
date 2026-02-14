from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

@dataclass(frozen=True)
class AnalysisResult:
    spike: bool
    headline: str
    reasons: List[str]      # 1–3 причины
    actions: List[Tuple[str, str, str]]  # (title, why, how)
    meta: Dict

def _pct(a: float, b: float) -> float:
    if b == 0:
        return 0.0
    return (a / b - 1.0) * 100.0

def detect_spike(now_kwh: Optional[float], prev_kwh: Optional[float],
                 now_money: Optional[float], prev_money: Optional[float]) -> Tuple[bool, Optional[float], str]:
    """
    Возвращает: (spike?, pct_change?, basis)
    basis: 'kwh'|'money'|'none'
    """
    if now_kwh is not None and prev_kwh is not None and prev_kwh > 0:
        pct = _pct(now_kwh, prev_kwh)
        spike = (now_kwh > prev_kwh * 1.15) or ((prev_kwh < 300) and (now_kwh - prev_kwh > 50))
        return spike, pct, "kwh"

    if now_money is not None and prev_money is not None and prev_money > 0:
        pct = _pct(now_money, prev_money)
        spike = now_money > prev_money * 1.15
        return spike, pct, "money"

    return False, None, "none"

def pick_reasons(profile: Dict, ctx: Dict, basis: str) -> List[str]:
    heating = (profile.get("heating") or "")
    people = (profile.get("people") or "")

    cold = ctx.get("cold")
    boiler = ctx.get("boiler")
    new_appliance = ctx.get("new_appliance")

    reasons: List[str] = []

    if heating == "electric" or cold is True:
        reasons.append("Электроотопление/обогрев работали дольше (холоднее).")

    if boiler is True:
        reasons.append("Нагрев воды (бойлер/тэн) даёт заметную базовую нагрузку.")

    if people in ("3-4", "5+") or ctx.get("more_time_home") is True:
        reasons.append("Больше времени дома/людей → чаще свет, готовка, техника.")

    if new_appliance is True:
        reasons.append("Новый прибор или чаще используете энергоёмкие режимы (стирка/сушка/готовка).")

    reasons.append("Часть расхода может уходить в «standby» и мелкие потребители (TV/приставка/зарядки).")

    if basis == "money":
        reasons.append("Если рост только в ₸ — возможно, сыграл тариф/перерасчёт, без изменения кВт*ч.")

    return reasons[:3]

# Каталог действий
ACTIONS = [
    ("timer_heater",
     "Поставить график/таймер на обогрев",
     "Ограничивает лишние часы работы — это чаще всего главный рычаг зимой.",
     "Сегодня: 2–3 окна времени (утро/вечер). Ночью — минимум/выключить, если можно."),
    ("lower_temp",
     "Снизить температуру обогрева на 1–2°C",
     "Даже небольшой спад температуры уменьшает потребление заметно на длинном интервале.",
     "Сегодня: уменьшите на 1°C, через сутки оцените кВт*ч/день."),
    ("seal_windows",
     "Уплотнить окна/щели",
     "Меньше теплопотерь → обогрев включается реже.",
     "За 1 день: уплотнитель/лента на проблемные места, особенно двери/окна."),
    ("boiler_5560",
     "Бойлер: выставить 55–60°C (не «макс»)",
     "Меньше циклов нагрева и потерь — часто даёт быстрый эффект.",
     "Сегодня: поставьте 55–60°C, проверьте через сутки."),
    ("standby_strip",
     "Отключать standby через удлинитель с кнопкой",
     "Срезает постоянную «фоновую» нагрузку.",
     "Сегодня: TV/приставка/зарядки на один удлинитель, выключать на ночь."),
    ("night_test",
     "Сделать «ночной тест»",
     "Быстро покажет скрытый базовый расход без активного использования.",
     "Сегодня: снимите показания вечером и утром (6–8 часов) и посмотрите кВт*ч."),
    ("wash_30_full",
     "Стирка: 30°C и полная загрузка",
     "Нагрев воды — один из самых дорогих режимов.",
     "В ближайшие 1–2 дня: 2–3 стирки так, сравните ощущения и расход."),
    ("kettle_volume",
     "Чайник: кипятить нужный объём",
     "Мелочь, но частые кипячения быстро набегают.",
     "Сегодня: наливайте только нужное количество."),
    ("fridge_settings",
     "Холодильник: +4…+5°C, морозилка −18°C + зазор от стены",
     "Неправильные настройки и плохая вентиляция повышают потребление.",
     "За 1 день: проверьте настройки, отодвиньте от стены, уберите наледь."),
]

def pick_top3_actions(profile: Dict, ctx: Dict) -> List[Tuple[str, str, str]]:
    heating = profile.get("heating")
    boiler = ctx.get("boiler") is True
    cold = ctx.get("cold") is True

    scores: Dict[str, int] = {}

    def add(action_id: str, pts: int):
        scores[action_id] = scores.get(action_id, 0) + pts

    if heating == "electric" or cold:
        add("timer_heater", 6)
        add("lower_temp", 4)
        add("seal_windows", 4)

    if boiler:
        add("boiler_5560", 6)

    add("standby_strip", 3)
    add("night_test", 3)
    add("wash_30_full", 2)
    add("fridge_settings", 2)
    add("kettle_volume", 1)

    if not scores:
        scores = {"standby_strip": 3, "night_test": 3, "wash_30_full": 2}

    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    chosen_ids = [aid for aid, _ in ranked[:3]]

    catalog = {a[0]: a for a in ACTIONS}
    out: List[Tuple[str, str, str]] = []
    for aid in chosen_ids:
        a = catalog.get(aid)
        if a:
            out.append((a[1], a[2], a[3]))
    return out

def make_analysis(profile: Dict, ctx: Dict,
                  now_kwh: Optional[float], prev_kwh: Optional[float],
                  now_money: Optional[float], prev_money: Optional[float]) -> AnalysisResult:
    spike, pct, basis = detect_spike(now_kwh, prev_kwh, now_money, prev_money)

    if pct is None:
        headline = "Данных для сравнения мало — дам диагностику по контексту."
    else:
        sign = "+" if pct >= 0 else ""
        headline = f"Вижу изменение примерно {sign}{pct:.0f}% по {'кВт*ч' if basis=='kwh' else 'сумме'}."

    reasons = pick_reasons(profile, ctx, basis)
    actions = pick_top3_actions(profile, ctx)

    meta = {"basis": basis, "pct": pct, "spike": spike}
    return AnalysisResult(spike=spike, headline=headline, reasons=reasons, actions=actions, meta=meta)

def savings_calc(before_kwh: Optional[float], before_days: int,
                 after_kwh: Optional[float], after_days: int,
                 tariff: Optional[float]) -> Dict:
    if before_kwh is None or after_kwh is None or before_days <= 0 or after_days <= 0:
        return {"ok": False, "msg": "Нужны кВт*ч за оба периода, чтобы корректно посчитать экономию."}

    before_per_day = before_kwh / before_days
    after_per_day = after_kwh / after_days
    delta_per_day = before_per_day - after_per_day
    delta_kwh = delta_per_day * after_days
    pct = 0.0 if before_per_day == 0 else (1.0 - after_per_day / before_per_day) * 100.0

    return {
        "ok": True,
        "before_per_day": before_per_day,
        "after_per_day": after_per_day,
        "delta_kwh": delta_kwh,
        "pct": pct,
        "delta_money": (delta_kwh * tariff) if (tariff is not None) else None
    }
