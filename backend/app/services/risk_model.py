"""Модель ризику: вердикт «виконання × ефект» замість формул ефективності.

Початкову оцінку ризику (ймовірність L₀ × наслідки C₀) дають люди — робоча група за Методологією НАЗК.
Система перевіряє її даними: чи виконано заходи і чи рухається індикатор ризику (KRI) до цілі.
Бал НАЗК система сама не змінює, лише пропонує переоцінку з підставами (правила P1, L-1, L+1).
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import audit, halfyear
from ..enums import FINAL_STATUSES, FlagStatus, MeasureStatus, ProgramStatus, RiskLevel, SignalType
from ..models import CorruptionRisk, Indicator, Measure, MeasurePeriod, Program, RiskSignal, local_date, utcnow

RULESET_VERSION = "2026-11.2"

NOISE_MIN_PP = 5.0  # δ для часток: не менше 5 в.п.
SELF_REPORT_FACTOR = 0.5  # позитивний прогрес за самозвітними даними
RRS_SIGNIFICANT, RRS_PARTIAL = 0.666, 0.333  # пороги ДАП 2023–2025 (категорія RRS і підстава L-1)
NO_CHANGE = 0.10  # менше 10 % шляху від бази до цілі — «без змін» (правило RF3 організаторів)
FCG_YELLOW, FCG_RED = 10.0, 25.0  # в.п.
NO_DATA_DAYS = 365  # «немає даних 2 періоди» (два півріччя)
INCIDENT_FLOOR = ((6, 4), (12, 3), (36, 2))  # інцидент молодший N міс. → ймовірність щонайменше L
REASSESS_STREAK = 2  # кварталів поспіль для підстави переоцінки
TRAINING_SECTION = 3

# Стан індикатора ризику і ризику в цілому.
ON_TRACK, LAGGING, NO_CHANGE_STATE, WORSENING, NO_DATA = "ON_TRACK", "LAGGING", "NO_CHANGE", "WORSENING", "NO_DATA"
EFFECT_UA = {
    ON_TRACK: "на траєкторії",
    LAGGING: "рухається, але відстає від графіка",
    NO_CHANGE_STATE: "без змін",
    WORSENING: "погіршення",
    NO_DATA: "немає даних",
}
MOVING = {ON_TRACK, LAGGING}

# Вердикт ризику: матриця «є виконані заходи» × «стан індикатора».
VERDICTS: dict[str, tuple[str, str]] = {  # код → (назва, колір)
    "WORKING": ("Заходи працюють", "green"),
    "FORMAL": ("Закрито «на папері»", "red"),
    "WORSE_DESPITE": ("Погіршення попри виконання", "red"),
    "EXTERNAL": ("Покращення без виконаних заходів", "gray"),
    "STAGNANT": ("Заходи не виконано, змін немає", "yellow"),
    "UNATTENDED": ("Ризик росте без реакції", "red"),
    "NO_DATA": ("Немає даних індикатора", "gray"),
    "NO_MEASURES": ("Немає заходів щодо ризику", "orange"),
}
_MATRIX = {
    (True, True): "WORKING", (True, NO_CHANGE_STATE): "FORMAL", (True, WORSENING): "WORSE_DESPITE",
    (False, True): "EXTERNAL", (False, NO_CHANGE_STATE): "STAGNANT", (False, WORSENING): "UNATTENDED",
}

SIGNAL_RULES: dict[SignalType, tuple[str, str, str]] = {  # code, label, colour
    SignalType.TARGET_NOT_REACHED: ("T1", "Ціль не досягнута", "yellow"),
    SignalType.INSUFFICIENT_DATA: ("D1", "Недостатньо даних", "gray"),
    SignalType.BASELINE_CHANGED: ("B1", "Змінено базу чи ціль", "orange"),
    SignalType.INCIDENT_FLOOR: ("P1", "Підстава переоцінити: підтверджений інцидент", "red"),
    SignalType.REASSESS_UP: ("L+1", "Підстава підвищити ймовірність", "orange"),
    SignalType.REASSESS_DOWN: ("L-1", "Підстава знизити ймовірність", "green"),
    SignalType.PRIORITY_VIOLATION: ("S1", "Порушення принципу пріоритетності НАЗК", "orange"),
    SignalType.RISK_DISPLACEMENT: ("X1", "Можливе витіснення ризику", "orange"),
    SignalType.EFFECT_NOT_CONFIRMED: ("G1", "Застаріле правило: ефективність не підтверджена", "gray"),
}
_LEVEL_SCORES = {RiskLevel.LOW: (1, 2), RiskLevel.MEDIUM: (2, 2), RiskLevel.HIGH: (3, 3), RiskLevel.CRITICAL: (4, 4)}


def _r(x: float | None, nd: int = 3) -> float | None:
    return None if x is None else round(x, nd)


def months_between(a: date, b: date) -> float:
    return (b - a).days / 30.4375


def add_months(d: date, months: int) -> date:
    y, m = divmod(d.month - 1 + months, 12)
    year, month = d.year + y, m + 1
    days = [31, 29 if year % 4 == 0 and (year % 100 != 0 or year % 400 == 0) else 28, 31, 30, 31, 30, 31, 31, 30, 31,
            30, 31][month - 1]
    return date(year, month, min(d.day, days))


def rrs_category(rrs: float | None) -> str:
    if rrs is None:
        return "немає даних"
    if rrs >= RRS_SIGNIFICANT:
        return "суттєве зниження"
    if rrs >= RRS_PARTIAL:
        return "часткове зниження"
    if rrs >= 0:
        return "незначне зниження"
    return "погіршення"


def fcg_color(fcg_pp: float) -> str:
    return "green" if fcg_pp < FCG_YELLOW else "yellow" if fcg_pp <= FCG_RED else "red"


def is_share(ind: Indicator) -> bool:
    return (ind.unit or "").strip().startswith("%")


def noise_threshold(ind: Indicator, n: int | None) -> float:
    """δ: set by hand, or for shares max(5 в.п.; 2·√(B(1−B)/n)); otherwise 0."""
    if ind.noise_threshold is not None:
        return float(ind.noise_threshold)
    if not is_share(ind):
        return 0.0
    b = min(max(float(ind.baseline) / 100, 0.0), 1.0)
    stat = 2 * math.sqrt(b * (1 - b) / n) * 100 if n else 0.0
    return max(NOISE_MIN_PP, stat)


def progress_state(p: float | None, expected: float | None) -> str:
    """Стан за прогресом p і очікуваним прогресом на дату (рівномірний рух від бази до цілі)."""
    if p is None:
        return NO_DATA
    if p < 0:
        return WORSENING
    if p < NO_CHANGE:
        return NO_CHANGE_STATE
    if expected is not None and p < expected:
        return LAGGING
    return ON_TRACK


def expected_progress(ind: Indicator, as_of: date, start: date | None) -> float | None:
    """Яку частку шляху від бази до цілі KRI мав би пройти на дату, якщо рухатися рівномірно до дедлайну цілі."""
    end = ind.target_date
    if start is None or end is None or end <= start:
        return None
    return min(1.0, max(0.0, (as_of - start).days / (end - start).days))


@dataclass
class KriResult:
    indicator: Indicator
    weight: float = 0.0  # normalised within the risk
    current: float | None = None
    measured_at: date | None = None
    sample_size: int | None = None
    delta: float = 0.0
    change: float | None = None  # C − B
    noise: bool = False  # |C − B| < δ → p = 0
    raw: float | None = None  # before noise/clip/self-report
    p: float | None = None
    self_report_discount: bool = False
    expected: float | None = None
    state: str = NO_DATA
    insufficient: list[str] = field(default_factory=list)

    @property
    def baseline(self) -> float:
        return float(self.indicator.baseline)

    @property
    def target(self) -> float:
        return float(self.indicator.target)


def kri_progress(ind: Indicator, as_of: date, weight: float = 1.0, start: date | None = None) -> KriResult:
    res = KriResult(indicator=ind, weight=weight)
    res.expected = expected_progress(ind, as_of, start)
    values = [v for v in ind.values if v.measured_at <= as_of]
    last = values[-1] if values else None
    if last is None:
        res.insufficient.append("немає жодного вимірювання")
        return res
    if (as_of - last.measured_at).days > NO_DATA_DAYS:
        res.insufficient.append(f"немає даних два періоди (останнє вимірювання {last.measured_at:%d.%m.%Y})")
    if ind.min_sample and (last.sample_size or 0) < ind.min_sample:
        res.insufficient.append(f"обсяг вибірки n = {last.sample_size or '—'} менший за мінімум {ind.min_sample}")
    b, t, c = res.baseline, res.target, float(last.value)
    res.current, res.measured_at, res.sample_size = c, last.measured_at, last.sample_size
    res.change = c - b
    res.delta = noise_threshold(ind, last.sample_size)
    if t == b:
        res.raw = 0.0
    elif ind.lower_is_better:
        res.raw = (b - c) / (b - t)
    else:
        res.raw = (c - b) / (t - b)
    res.noise = abs(c - b) < res.delta
    p = 0.0 if res.noise else max(-1.0, min(1.0, res.raw))
    if p > 0 and not ind.independent:
        p *= SELF_REPORT_FACTOR
        res.self_report_discount = True
    res.p = p
    res.state = progress_state(p, res.expected)
    return res


def rrs_of(kris: list[KriResult]) -> float | None:
    """RRS = Σ wᵢ·pᵢ over KRIs with data (weights re-normalised over them)."""
    known = [k for k in kris if k.p is not None]
    total = sum(float(k.indicator.weight or 0) for k in known)
    if not known or total <= 0:
        return None
    return sum(float(k.indicator.weight or 0) / total * k.p for k in known)


def expected_of(kris: list[KriResult]) -> float | None:
    known = [k for k in kris if k.p is not None and k.expected is not None]
    total = sum(float(k.indicator.weight or 0) for k in known)
    if not known or total <= 0:
        return None
    return sum(float(k.indicator.weight or 0) / total * k.expected for k in known)


def program_start(risk: CorruptionRisk) -> date | None:
    starts = [m.section.program.period_start for m in approved_measures(risk)]
    return min(starts) if starts else None


def risk_kris(risk: CorruptionRisk, as_of: date, start: date | None = None) -> list[KriResult]:
    inds = list(risk.indicators)
    total = sum(float(i.weight or 0) for i in inds) or 1.0
    return [kri_progress(i, as_of, float(i.weight or 0) / total, start) for i in inds]


def has_document(m: Measure, p: MeasurePeriod) -> bool:
    if not p.evidence:
        return False
    form = {x.strip().lower() for x in (m.evidence_form or "").split(",") if x.strip()}
    return not form or any((e.doc_type or "").strip().lower() in form for e in p.evidence)


def closed_period(m: Measure, as_of: date) -> MeasurePeriod | None:
    done = [p for p in m.periods if p.status in FINAL_STATUSES and halfyear.start(p.period) <= as_of]
    return done[-1] if done else None


def is_submitted(p: MeasurePeriod) -> bool:
    """Виконавець подав результат як виконаний (опис результату, а не причина невиконання), координатор ще не
    погодив."""
    return p.status == MeasureStatus.ON_REVIEW and bool((p.result_description or "").strip())


def claimed_period(m: Measure, as_of: date) -> MeasurePeriod | None:
    """Останній період, який виконавець заявив виконаним: «Виконано» або подано на перевірку з описом результату."""
    ps = [p for p in m.periods if halfyear.start(p.period) <= as_of
          and (p.status == MeasureStatus.DONE or is_submitted(p))]
    return ps[-1] if ps else None


def completed_on(p: MeasurePeriod) -> date | None:
    if p.actual_date:
        return p.actual_date
    if p.approvals:
        return local_date(p.approvals[-1].created_at)
    return local_date(p.updates[-1].created_at) if p.updates else None


def status_share(m: Measure, as_of: date) -> float:
    p = closed_period(m, as_of)
    return 1.0 if p and p.status == MeasureStatus.DONE else 0.5 if p and p.status == MeasureStatus.PARTIAL else 0.0


def approved_measures(risk: CorruptionRisk) -> list[Measure]:
    return [m for m in risk.measures if m.section.program.status == ProgramStatus.APPROVED]


@dataclass
class Hint:
    """Підстава для переоцінки ймовірності робочою групою (система бал не змінює)."""
    rule: str
    text: str
    suggested: int  # запропонована ймовірність
    inputs: dict
    source: str = ""


@dataclass
class MeasureState:
    measure: Measure
    period: MeasurePeriod | None
    done: bool  # «Виконано» або подано як виконаний
    pending: bool  # подано, ще не погоджено
    completed: date | None


@dataclass
class Assessment:
    risk: CorruptionRisk
    as_of: date
    probability0: int
    impact0: int
    kris: list[KriResult]
    rrs: float | None
    expected: float | None
    effect: str
    measures: list[MeasureState]
    verdict: str
    preliminary: bool  # є виконані заходи, лаг ефекту яких ще не минув
    effect_due: date | None  # коли мине лаг останнього виконаного заходу
    hints: list[Hint]
    signals: list[tuple[SignalType, Indicator | None, dict, str]]

    @property
    def inherent(self) -> int:
        return self.probability0 * self.impact0

    @property
    def done_count(self) -> int:
        return sum(1 for x in self.measures if x.done)


def level_problem(level: RiskLevel | None, probability: int | None, impact: int | None) -> str | None:
    """Рівень ризику має відповідати балу L·C за Методологією НАЗК (1–2 / 3–4 / 6–9 / 12–16)."""
    if (probability is None) != (impact is None):
        return "Вкажіть і ймовірність, і наслідки, або жодного"
    if probability is None:
        return None if level else "Вкажіть рівень ризику або бали ймовірності й наслідків"
    want = RiskLevel.from_score(probability * impact)
    if level and level != want:
        return (f"Рівень «{level.value}» не відповідає балу {probability}·{impact} = {probability * impact} "
                f"(за Методологією НАЗК — {want.value})")
    return None


def kri_problem(baseline, target, lower_is_better: bool | None) -> str | None:
    """Ціль KRI має відрізнятися від бази і лежати в напрямі покращення."""
    if baseline is None or target is None:
        return None
    if target == baseline:
        return "Ціль індикатора дорівнює базі: прогрес порахувати неможливо"
    if lower_is_better is True and target > baseline:
        return "Напрям «менше — краще», а ціль більша за базу"
    if lower_is_better is False and target < baseline:
        return "Напрям «більше — краще», а ціль менша за базу"
    return None


def base_scores(risk: CorruptionRisk) -> tuple[int, int]:
    if risk.probability and risk.impact:
        return risk.probability, risk.impact
    return _LEVEL_SCORES[risk.level]


def _quarter_ends(start: date, end: date) -> list[date]:
    out, y, q = [], start.year, (start.month - 1) // 3
    while True:
        m = 3 * (q + 1)
        d = date(y, m, 31 if m in (3, 12) else 30)
        if d > end:
            return out
        if d >= start:
            out.append(d)
        q += 1
        if q == 4:
            y, q = y + 1, 0


def reassessment_hints(risk: CorruptionRisk, as_of: date, start: date | None) -> list[Hint]:
    """Симетричні підстави: RRS ≥ 0,666 або RRS < 0 два квартали поспіль; підтверджений інцидент — підлога P1."""
    l0, _ = base_scores(risk)
    hints: list[Hint] = []
    quarters = _quarter_ends(start, as_of)[-REASSESS_STREAK:] if start else []
    if len(quarters) == REASSESS_STREAK:
        values = [rrs_of(risk_kris(risk, q, start)) for q in quarters]
        dates = ", ".join(f"{q:%d.%m.%Y}" for q in quarters)
        shown = [_r(v) for v in values]
        if all(v is not None and v >= RRS_SIGNIFICANT for v in values) and l0 > 1:
            hints.append(Hint("L-1", f"Ризик суттєво знизився два квартали поспіль (RRS {shown} на {dates}): "
                                     f"підстава розглянути зниження ймовірності {l0} → {l0 - 1}.",
                              l0 - 1, {"rrs": shown, "dates": [q.isoformat() for q in quarters]}))
        if all(v is not None and v < 0 for v in values) and l0 < 4:
            hints.append(Hint("L+1", f"Ризик погіршувався два квартали поспіль (RRS {shown} на {dates}): "
                                     f"підстава розглянути підвищення ймовірності {l0} → {l0 + 1}.",
                              l0 + 1, {"rrs": shown, "dates": [q.isoformat() for q in quarters]}))
    best = None
    for inc in risk.incidents:
        if not inc.confirmed or inc.occurred_on > as_of:
            continue
        age = months_between(inc.occurred_on, as_of)
        hit = next(((mo, f) for mo, f in INCIDENT_FLOOR if age <= mo), None)
        if hit and hit[1] > l0 and (best is None or hit[1] > best[0][1]):
            best = (hit, inc, age)
    if best:
        (months, floor), inc, age = best
        hints.append(Hint("P1", f"Підтверджений інцидент {inc.occurred_on:%d.%m.%Y} молодший {months} міс.: за "
                                f"критеріями НАЗК ймовірність щонайменше {floor}, а в реєстрі {l0} — підстава "
                                f"переоцінити ризик.",
                          floor, {"incidentDate": inc.occurred_on.isoformat(), "ageMonths": _r(age, 1),
                                  "probability": l0, "floor": floor}, inc.source))
    return hints


def _measure_states(risk: CorruptionRisk, as_of: date) -> list[MeasureState]:
    out = []
    for m in approved_measures(risk):
        claimed = claimed_period(m, as_of)
        p = claimed or closed_period(m, as_of) or m.period_for(as_of)
        out.append(MeasureState(m, p, claimed is not None, claimed is not None and is_submitted(claimed),
                                completed_on(claimed) if claimed else None))
    return out


def verdict_of(has_measures: bool, any_done: bool, effect: str) -> str:
    if not has_measures:
        return "NO_MEASURES"
    if effect == NO_DATA:
        return "NO_DATA"
    return _MATRIX[(any_done, True if effect in MOVING else effect)]


def assess(risk: CorruptionRisk, as_of: date) -> Assessment:
    start = program_start(risk)
    kris = risk_kris(risk, as_of, start)
    rrs = rrs_of(kris)
    expected = expected_of(kris)
    effect = progress_state(rrs, expected)
    states = _measure_states(risk, as_of)
    done = [x for x in states if x.done]
    lag = max((k.indicator.lag_months for k in kris), default=0)
    due = max((add_months(x.completed, lag) for x in done if x.completed), default=None)
    l0, c0 = base_scores(risk)
    a = Assessment(risk, as_of, l0, c0, kris, rrs, expected, effect, states,
                   verdict_of(bool(states), bool(done), effect), bool(due and due > as_of), due,
                   reassessment_hints(risk, as_of, start), [])
    a.signals = _signals(a)
    return a


_HINT_SIGNAL = {"P1": SignalType.INCIDENT_FLOOR, "L+1": SignalType.REASSESS_UP, "L-1": SignalType.REASSESS_DOWN}


def _signals(a: Assessment) -> list[tuple[SignalType, Indicator | None, dict, str]]:
    out = []
    for k in a.kris:
        ind = k.indicator
        if ind.target_date and ind.target_date <= a.as_of and (k.p is None or k.p < 1):
            out.append((SignalType.TARGET_NOT_REACHED, ind,
                        {"targetDate": ind.target_date.isoformat(), "p": _r(k.p), "target": k.target,
                         "current": k.current},
                        f"Настав дедлайн цілі {ind.target_date:%d.%m.%Y}, а прогрес «{ind.name}» p = "
                        f"{_r(k.p, 2) if k.p is not None else 'немає даних'} < 1."))
        if k.insufficient:
            out.append((SignalType.INSUFFICIENT_DATA, ind, {"reasons": k.insufficient},
                        f"KRI «{ind.name}»: " + "; ".join(k.insufficient) + "."))
        if ind.baseline_hash and ind.baseline_hash != ind.baseline_digest():
            out.append((SignalType.BASELINE_CHANGED, ind,
                        {"frozenAt": ind.baseline_frozen_at.isoformat() if ind.baseline_frozen_at else None,
                         "baseline": k.baseline, "target": k.target},
                        f"Базу або ціль KRI «{ind.name}» змінено після затвердження програми "
                        f"(зафіксовано {ind.baseline_frozen_at:%d.%m.%Y})." if ind.baseline_frozen_at else
                        f"Базу або ціль KRI «{ind.name}» змінено після затвердження програми."))
        pair = ind.paired_with
        if pair is not None and k.p is not None and k.p > 0:
            pk = kri_progress(pair, a.as_of)
            if pk.p is not None and pk.p < 0:
                out.append((SignalType.RISK_DISPLACEMENT, ind,
                            {"primary": ind.name, "primaryP": _r(k.p), "paired": pair.name, "pairedP": _r(pk.p),
                             "pairedDelta": _r(pk.delta)},
                            f"«{ind.name}» покращився (p = {k.p:.2f}), а парний «{pair.name}» погіршився понад "
                            f"поріг (p = {pk.p:.2f}): ризик міг перетекти."))
    for h in a.hints:
        out.append((_HINT_SIGNAL[h.rule], None, {**h.inputs, "suggested": h.suggested, "source": h.source}, h.text))
    level0 = RiskLevel.from_score(a.inherent)
    ms = [x.measure for x in a.measures]
    if level0 in (RiskLevel.CRITICAL, RiskLevel.HIGH) and ms and all(m.section.number == TRAINING_SECTION for m in ms):
        out.append((SignalType.PRIORITY_VIOLATION, None, {"level": level0.value, "measures": [m.code for m in ms]},
                    "Ризик критичного або високого рівня закривається лише навчальними заходами (розділ 3)."))
    return out


def formal_closure_hit(m: Measure, p: MeasurePeriod, as_of: date) -> tuple[str, dict, str] | None:
    """F1 / F2 за правилом організаторів (RF3): захід виконано, а ризик пройшов < 10 % шляху або погіршився.
    Лаг ефекту не блокує висновок, а робить його попереднім."""
    if m.risk is None or not (p.status == MeasureStatus.DONE or is_submitted(p)):
        return None
    risk = m.risk
    kris = risk_kris(risk, as_of, program_start(risk))
    done_on = completed_on(p) or as_of
    lag = max((k.indicator.lag_months for k in kris), default=0)
    due = add_months(done_on, lag)
    preliminary = due > as_of
    facts = {"period": p.period, "completedOn": done_on.isoformat(), "lagMonths": lag,
             "monthsSince": _r(months_between(done_on, as_of), 1), "effectDue": due.isoformat(),
             "preliminary": preliminary, "pendingApproval": is_submitted(p), "risk": risk.code}
    tail = (f" Висновок попередній: лаг ефекту {lag} міс. мине {due:%d.%m.%Y}." if preliminary else "") + \
           (" Результат ще на перевірці координатора." if is_submitted(p) else "")
    what = "подано як виконаний" if is_submitted(p) else "виконано"
    if not kris:
        return ("F1", {**facts, "kri": None},
                f"Захід {what}, але ризик {risk.code} не має індикатора — зменшення ризику не підтверджено.{tail}")
    rrs = rrs_of(kris)
    facts |= {"rrs": _r(rrs), "threshold": NO_CHANGE,
              "kri": [{"name": k.indicator.name, "baseline": k.baseline, "target": k.target, "current": k.current,
                       "delta": _r(k.delta), "noise": k.noise, "p": _r(k.p)} for k in kris]}
    if rrs is None:
        return ("F1", facts, f"Захід {what}, а вимірювань індикатора ризику {risk.code} немає.{tail}")
    if rrs < 0:
        return ("F2", facts, f"Захід {what}, а ризик {risk.code} погіршився: RRS = {rrs:.2f} < 0.{tail}")
    if rrs < NO_CHANGE:
        k = kris[0]
        shown = f"{k.baseline:g} → {k.current:g} при цілі {k.target:g}, " if len(kris) == 1 and k.current is not None \
            else ""
        return ("F1", facts, f"Захід {what}, а індикатор ризику {risk.code} майже не змінився: {shown}пройдено "
                             f"{max(rrs, 0):.0%} шляху (< {NO_CHANGE:.0%}).{tail}")
    return None


@dataclass
class ProgramMetrics:
    as_of: date
    assessments: list[Assessment]
    pri: float
    exec: float
    fcg_pp: float
    color: str
    top_contributor: Assessment | None
    weakest: Assessment | None
    sub_index: float | None
    sub_index_count: int
    shares: dict = field(default_factory=dict)  # risk id → частка виконаних заходів

    @property
    def verdict_counts(self) -> dict[str, int]:
        out = dict.fromkeys(VERDICTS, 0)
        for a in self.assessments:
            out[a.verdict] += 1
        return out


def program_risks(db: Session, program: Program) -> list[CorruptionRisk]:
    ids = {m.risk_id for sec in program.sections for m in sec.measures if m.risk_id}
    return list(db.scalars(select(CorruptionRisk).where(CorruptionRisk.id.in_(ids)).order_by(CorruptionRisk.code)))


def program_metrics(db: Session, program: Program, as_of: date, see=None) -> ProgramMetrics:
    """`see` (services.scope.Scope): only risks and measures in the user's scope count.
    PRI = Σ I·RRS / Σ I, EXEC = Σ I·частка виконаних / Σ I, FCG = EXEC − PRI."""
    keep = (lambda m: True) if see is None else see.measure
    items = [assess(r, as_of) for r in program_risks(db, program) if see is None or see.risk(r)]
    weights = sum(a.inherent for a in items) or 1
    shares = {}
    for a in items:
        ms = [x.measure for x in a.measures if keep(x.measure)]
        shares[a.risk.id] = sum(status_share(m, as_of) for m in ms) / len(ms) if ms else 0.0
    pri = sum(a.inherent * (a.rrs or 0.0) for a in items) / weights
    exe = sum(a.inherent * shares[a.risk.id] for a in items) / weights
    fcg = (exe - pri) * 100
    top = max(items, key=lambda a: a.inherent * (shares[a.risk.id] - (a.rrs or 0.0)), default=None)
    critical = [a for a in items if a.inherent >= 12 and a.rrs is not None]
    weakest = min(critical, key=lambda a: a.rrs, default=None)
    own = [m.indicator for sec in program.sections if sec.number != 2 for m in sec.measures
           if m.risk_id is None and m.indicator is not None and keep(m)]
    ps = [k.p for k in (kri_progress(i, as_of) for i in own) if k.p is not None]
    return ProgramMetrics(as_of, items, pri, exe, fcg, fcg_color(fcg), top, weakest,
                          sum(ps) / len(ps) if ps else None, len(ps), shares)


def evaluate_signals(db: Session, today: date, risks: list[CorruptionRisk] | None = None) -> tuple[int, int]:
    if risks is None:
        risks = list(db.scalars(select(CorruptionRisk)))
    opened = resolved = 0
    for risk in risks:
        want = {(t, ind.id if ind else None): (facts, text) for t, ind, facts, text in assess(risk, today).signals}
        current = {(s.type, s.indicator_id): s for s in db.scalars(
            select(RiskSignal).where(RiskSignal.risk_id == risk.id, RiskSignal.status == FlagStatus.OPEN))}
        for key, s in current.items():
            if key in want:
                s.facts, s.explanation = want[key]
            else:
                s.status, s.resolved_at = FlagStatus.RESOLVED, utcnow()
                audit.record(db, None, "risk_signal", s.id, "auto_resolve", {"status": "OPEN"}, {"status": "RESOLVED"})
                resolved += 1
        for (t, ind_id), (facts, text) in want.items():
            if (t, ind_id) in current:
                continue
            s = RiskSignal(risk_id=risk.id, indicator_id=ind_id, type=t, rule_code=SIGNAL_RULES[t][0],
                           facts=facts, explanation=text)
            db.add(s)
            db.flush()
            audit.record(db, None, "risk_signal", s.id, "open", None,
                         {"type": t.value, "ruleCode": s.rule_code, "riskId": str(risk.id)})
            opened += 1
    db.flush()
    return opened, resolved


def freeze_baselines(indicators: list[Indicator]) -> None:
    now = utcnow()
    for i in indicators:
        i.freeze_baseline(now)


def program_indicators(program: Program) -> list[Indicator]:
    out: dict = {}
    for sec in program.sections:
        for m in sec.measures:
            if m.indicator is not None:
                out[m.indicator.id] = m.indicator
            if m.risk is not None:
                out.update({i.id: i for i in m.risk.indicators})
    return list(out.values())
