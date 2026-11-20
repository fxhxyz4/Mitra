import uuid
from collections import Counter
from datetime import date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import halfyear
from ..enums import LEVEL_UA, STATUS_UA, Decision, FlagStatus, FlagType, MeasureStatus, RecStatus
from ..models import CorruptionRisk, Indicator, Measure, MeasurePeriod, OrgUnit, Program, Recommendation, RiskFlag, local_date
from ..schemas import analytics as a
from .dashboards import program_measures


def _pct(x: int, total: int) -> float:
    return round(100 * x / total, 1) if total else 0.0


def _day(dt: datetime) -> date:
    return local_date(dt)


def _all_periods(ms: list[Measure]) -> list[MeasurePeriod]:
    return [p for m in ms for p in m.periods]


def on_time(p: MeasurePeriod) -> bool:
    return p.status == MeasureStatus.DONE and p.actual_date is not None and p.actual_date <= p.measure.deadline_for(p)


def review_days(periods: list[MeasurePeriod]) -> float | None:
    spans = []
    for p in periods:
        for ap in p.approvals:
            sent = [u.created_at for u in p.updates
                    if u.status_to == MeasureStatus.ON_REVIEW and u.created_at <= ap.created_at]
            if sent:
                spans.append((ap.created_at - max(sent)).total_seconds() / 86400)
    return round(sum(spans) / len(spans), 1) if spans else None


def indicator_series(ind: Indicator) -> a.IndicatorSeries:
    cur = ind.current
    progress = None
    if cur is not None and ind.target != ind.baseline:
        progress = round(float((cur - ind.baseline) / (ind.target - ind.baseline)) * 100, 1)
        progress = max(0.0, min(100.0, progress))
    return a.IndicatorSeries(
        id=ind.id, name=ind.name, unit=ind.unit, baseline=ind.baseline, target=ind.target, current=cur,
        progress_percent=progress, is_improved=ind.is_improved(), is_target_reached=ind.is_target_reached(),
        values=[a.IndicatorPoint(date=v.measured_at, value=v.value) for v in ind.values],
    )


def _status_at(p: MeasurePeriod, at: date) -> MeasureStatus | None:
    st = None
    for u in p.updates:
        if _day(u.created_at) <= at:
            st = u.status_to
    return st


def _weeks(today: date, weeks: int) -> list[date]:
    return [today - timedelta(days=7 * i) for i in range(weeks - 1, -1, -1)]


def status_trend(ms: list[Measure], today: date, weeks: int) -> list[a.StatusPoint]:
    out = []
    for d in _weeks(today, weeks):
        c = Counter()
        for m in ms:
            p = m.period_for(d)
            st = _status_at(p, d) if p else None
            if st:
                c[st.value] += 1
        out.append(a.StatusPoint(date=d, counts={s.value: c.get(s.value, 0) for s in MeasureStatus}))
    return out


def flag_trend(flags: list[RiskFlag], today: date, weeks: int) -> list[a.FlagPoint]:
    out = []
    for d in _weeks(today, weeks):
        start = d - timedelta(days=6)
        opened = sum(1 for f in flags if start <= _day(f.created_at) <= d)
        resolved = sum(1 for f in flags if f.resolved_at and start <= _day(f.resolved_at) <= d)
        still_open = sum(1 for f in flags if _day(f.created_at) <= d and (not f.resolved_at or _day(f.resolved_at) > d))
        out.append(a.FlagPoint(date=d, opened=opened, resolved=resolved, open=still_open))
    return out


def risk_dynamics(db: Session, ms: list[Measure], today: date) -> list[a.RiskDynamics]:
    ids = {m.risk_id for m in ms if m.risk_id}
    out = []
    for r in db.scalars(select(CorruptionRisk).where(CorruptionRisk.id.in_(ids)).order_by(CorruptionRisk.code)):
        rm = [m for m in ms if m.risk_id == r.id]
        series = [indicator_series(i) for i in r.indicators]
        out.append(a.RiskDynamics(
            id=r.id, code=r.code, description=r.description, level=r.level, measures_total=len(rm),
            measures_done=sum(1 for m in rm if (p := m.period_for(today)) and p.status == MeasureStatus.DONE),
            reduced=bool(series) and all(i.is_improved for i in series),
            formal_closures=sum(1 for m in rm for f in m.flags
                                if f.type == FlagType.FORMAL_CLOSURE and f.status == FlagStatus.OPEN),
            indicators=series,
        ))
    return out


def unit_stats(db: Session, ms: list[Measure], today: date) -> list[a.UnitStats]:
    by_unit: dict[uuid.UUID, list[Measure]] = {}
    for m in ms:
        if m.responsible:
            by_unit.setdefault(m.responsible.org_unit_id, []).append(m)
    out = []
    for uid, items in by_unit.items():
        cur = [p for m in items if (p := m.period_for(today))]
        done_all = [p for m in items for p in m.periods if p.status == MeasureStatus.DONE]
        out.append(a.UnitStats(
            org_unit_id=uid, name=db.get(OrgUnit, uid).name, total=len(items),
            done=sum(p.status == MeasureStatus.DONE for p in cur),
            overdue=sum(m.is_overdue(today) for m in items),
            returned=sum(1 for m in items for p in m.periods for ap in p.approvals if ap.decision == Decision.RETURNED),
            open_flags=sum(1 for m in items for f in m.flags if f.status == FlagStatus.OPEN),
            on_time_percent=_pct(sum(on_time(p) for p in done_all), len(done_all)),
        ))
    return sorted(out, key=lambda u: u.name)


def kpis(db: Session, ms: list[Measure], risks: list[a.RiskDynamics], today: date) -> a.Kpis:
    cur = [p for m in ms if (p := m.period_for(today))]
    by = Counter(p.status for p in cur)
    periods = _all_periods(ms)
    done_all = [p for p in periods if p.status == MeasureStatus.DONE]
    approvals = [ap for p in periods for ap in p.approvals]
    mids = {m.id for m in ms}
    recs = [r for r in db.scalars(select(Recommendation)) if r.measure_id in mids]
    return a.Kpis(
        measures_total=len(ms),
        done=by[MeasureStatus.DONE],
        not_done=by[MeasureStatus.NOT_DONE],
        overdue=sum(m.is_overdue(today) for m in ms),
        on_review=by[MeasureStatus.ON_REVIEW],
        returned=by[MeasureStatus.RETURNED],
        done_percent=_pct(by[MeasureStatus.DONE], len(ms)),
        on_time_percent=_pct(sum(on_time(p) for p in done_all), len(done_all)),
        evidence_coverage_percent=_pct(sum(1 for p in done_all if p.evidence), len(done_all)),
        return_rate_percent=_pct(sum(ap.decision == Decision.RETURNED for ap in approvals), len(approvals)),
        avg_review_days=review_days(periods),
        risks_total=len(risks),
        risks_reduced=sum(r.reduced for r in risks),
        open_flags=sum(1 for m in ms for f in m.flags if f.status == FlagStatus.OPEN),
        recommendations_proposed=sum(r.status == RecStatus.PROPOSED for r in recs),
        recommendations_accepted=sum(r.status in (RecStatus.ACCEPTED, RecStatus.DONE) for r in recs),
    )


def overview(db: Session, program: Program, today: date, weeks: int = 12) -> a.AnalyticsOverview:
    ms = program_measures(db, program)
    risks = risk_dynamics(db, ms, today)
    flags = [f for m in ms for f in m.flags]
    sections = []
    for sec in program.sections:
        sm = [m for m in ms if m.section_id == sec.id]
        done = sum(1 for m in sm if (p := m.period_for(today)) and p.status == MeasureStatus.DONE)
        sections.append(a.SectionStats(
            number=sec.number, title=sec.title, total=len(sm), done=done,
            overdue=sum(m.is_overdue(today) for m in sm),
            open_flags=sum(1 for m in sm for f in m.flags if f.status == FlagStatus.OPEN),
            done_percent=_pct(done, len(sm)),
        ))
    open_types = Counter(f.type.value for f in flags if f.status == FlagStatus.OPEN)
    return a.AnalyticsOverview(
        program_id=program.id,
        program_title=program.title,
        as_of=today,
        period=halfyear.of(today),
        kpis=kpis(db, ms, risks, today),
        status_trend=status_trend(ms, today, weeks),
        flag_trend=flag_trend(flags, today, weeks),
        risks=risks,
        sections=sections,
        units=unit_stats(db, ms, today),
        flags_by_type={t.value: open_types.get(t.value, 0) for t in FlagType},
    )


KPI_LABELS = {
    "measures_total": "Заходів у програмі",
    "done": "Виконано",
    "not_done": "Не виконано",
    "overdue": "Прострочено",
    "on_review": "На перевірці",
    "returned": "Повернено на доопрацювання",
    "done_percent": "Частка виконаних, %",
    "on_time_percent": "Виконано вчасно, %",
    "evidence_coverage_percent": "Виконані з підтвердними матеріалами, %",
    "return_rate_percent": "Частка повернень, %",
    "avg_review_days": "Середній час перевірки, дн.",
    "risks_total": "Корупційних ризиків",
    "risks_reduced": "Ризиків зменшено (за індикаторами)",
    "open_flags": "Відкритих Risk Flags",
    "recommendations_proposed": "Рекомендацій очікують рішення",
    "recommendations_accepted": "Рекомендацій прийнято",
}


def export_tables(o: a.AnalyticsOverview) -> dict[str, list[list]]:
    k = o.kpis.model_dump()
    statuses = [s.value for s in MeasureStatus]
    return {
        "Показники": [["Показник", "Значення"]] + [[KPI_LABELS[f], k[f]] for f in KPI_LABELS],
        "Розділи": [["№", "Розділ", "Заходів", "Виконано", "Прострочено", "Risk Flags", "Виконано, %"]]
        + [[s.number, s.title, s.total, s.done, s.overdue, s.open_flags, s.done_percent] for s in o.sections],
        "Підрозділи": [["Підрозділ", "Заходів", "Виконано", "Прострочено", "Повернень", "Risk Flags", "Вчасно, %"]]
        + [[u.name, u.total, u.done, u.overdue, u.returned, u.open_flags, u.on_time_percent] for u in o.units],
        "Ризики": [["Код", "Ризик", "Рівень", "Заходів", "Виконано", "Зменшено", "Індикатор", "Базове", "Ціль",
                    "Поточне", "Прогрес, %"]]
        + [[r.code, r.description, LEVEL_UA[r.level], r.measures_total, r.measures_done, "так" if r.reduced else "ні",
            i.name, float(i.baseline), float(i.target), float(i.current) if i.current is not None else None,
            i.progress_percent] for r in o.risks for i in (r.indicators or [None]) if i]
        + [[r.code, r.description, LEVEL_UA[r.level], r.measures_total, r.measures_done, "ні", "—", None, None, None, None]
           for r in o.risks if not r.indicators],
        "Динаміка статусів": [["Дата"] + [STATUS_UA[s] for s in statuses]]
        + [[p.date.isoformat()] + [p.counts[s] for s in statuses] for p in o.status_trend],
        "Динаміка Risk Flags": [["Тиждень до", "Відкрито", "Знято", "Відкритих на дату"]]
        + [[p.date.isoformat(), p.opened, p.resolved, p.open] for p in o.flag_trend],
    }
