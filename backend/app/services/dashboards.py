import uuid
from collections import Counter
from datetime import date, timedelta
from typing import TYPE_CHECKING

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import halfyear
from ..auth import is_assigned
from ..enums import FINAL_STATUSES, FlagStatus, FlagType, MeasureStatus, ProgramStatus, RecStatus, RiskLevel
from ..models import CorruptionRisk, Measure, MeasurePeriod, OrgUnit, Program, Recommendation, Reminder, Section, User
from ..schemas import domain as s
from ..schemas.common import CamelModel
from .mappers import flag_out, indicator_out, measure_item


if TYPE_CHECKING:
    from .scope import Scope


class NonExecutionRisk(CamelModel):
    level: RiskLevel
    reasons: list[str]


class MeasureWithRisk(s.MeasureListItem):
    non_execution_risk: NonExecutionRisk


class ReturnedItem(CamelModel):
    measure: s.MeasureListItem
    comment: str


class ExecutorDashboard(CamelModel):
    upcoming: list[MeasureWithRisk]  # мої заходи на найближчі 30 днів
    returned: list[ReturnedItem]  # повернені із зауваженнями
    overdue: list[s.MeasureListItem]
    reminders: list[s.ReminderOut]
    total_mine: int


class SectionProgress(CamelModel):
    number: int
    title: str
    total: int
    by_status: dict[str, int]
    done_percent: float
    overdue: int


class CalendarItem(CamelModel):
    date: date
    measure_id: uuid.UUID
    code: str
    title: str
    status: MeasureStatus | None
    is_overdue: bool


class ReportReadiness(CamelModel):
    period: str
    total: int
    ready: int
    percent: float
    missing: list[s.MeasureListItem]


class CoordinatorDashboard(CamelModel):
    program_id: uuid.UUID
    review_queue: list[s.MeasureListItem]
    flags_by_type: dict[str, int]
    open_flags: list[s.RiskFlagOut]
    progress_by_section: list[SectionProgress]
    calendar: list[CalendarItem]
    report_readiness: ReportReadiness


class Overall(CamelModel):
    total: int
    by_status: dict[str, int]
    done_percent: float
    overdue: int
    risks_total: int
    risks_reduced: int
    open_flags: int


class RiskState(CamelModel):
    id: uuid.UUID
    code: str
    description: str
    level: RiskLevel
    measures_total: int
    measures_done: int
    indicators: list[s.IndicatorOut]
    reduced: bool


class UnitCell(CamelModel):
    org_unit_id: uuid.UUID
    name: str
    total: int
    overdue: int
    open_flags: int
    level: RiskLevel
    reasons: list[str]


class ExecutiveDashboard(CamelModel):
    program_id: uuid.UUID
    overall: Overall
    critical: list[MeasureWithRisk]
    risks: list[RiskState]  # стан корупційних ризиків: до і після
    units: list[UnitCell]  # карта ризику невиконання, без рейтингування
    upcoming_deadlines: list[CalendarItem]
    recommendations: list[s.RecommendationOut]
    flags_by_type: dict[str, int]


class UnitDashboard(CamelModel):
    org_unit_id: uuid.UUID
    name: str
    cell: UnitCell
    measures: list[MeasureWithRisk]


_ORDER = {RiskLevel.LOW: 0, RiskLevel.MEDIUM: 1, RiskLevel.HIGH: 2, RiskLevel.CRITICAL: 3}


def has_progress(p: MeasurePeriod) -> bool:
    # System transitions (programme approval, start date) have no author; only the executor's entries count.
    return any(u.author_id is not None and u.status_to == MeasureStatus.IN_PROGRESS for u in p.updates)


def non_execution_risk(m: Measure, today: date) -> NonExecutionRisk:
    p = m.period_for(today)
    if p is None or p.status in FINAL_STATUSES:
        return NonExecutionRisk(level=RiskLevel.LOW, reasons=["Період закрито"] if p else [])
    deadline = m.deadline_for(p)
    days = (deadline - today).days
    high, med = [], []
    if days < 0:
        high.append(f"Строк минув {-days} дн. тому")
    if p.status == MeasureStatus.RETURNED and days <= 14:
        high.append(f"Повернено на доопрацювання, до строку {days} дн.")
    if p.status in (MeasureStatus.PLANNED, MeasureStatus.IN_PROGRESS) and 0 <= days <= 14 and not has_progress(p):
        high.append(f"До строку {days} дн., проміжних результатів немає")
    if 0 <= days <= 30 and p.status != MeasureStatus.ON_REVIEW:
        med.append(f"До строку {days} дн.")
    n_flags = sum(1 for f in m.flags if f.status == FlagStatus.OPEN)
    if n_flags:
        med.append(f"Відкритих Risk Flags: {n_flags}")
    if high:
        return NonExecutionRisk(level=RiskLevel.HIGH, reasons=high + med)
    if med:
        return NonExecutionRisk(level=RiskLevel.MEDIUM, reasons=med)
    return NonExecutionRisk(level=RiskLevel.LOW, reasons=[])


def _with_risk(m: Measure, today: date) -> MeasureWithRisk:
    return MeasureWithRisk(**measure_item(m, today).model_dump(), non_execution_risk=non_execution_risk(m, today))


def resolve_program(db: Session, program_id: uuid.UUID | None) -> Program:
    if program_id:
        p = db.get(Program, program_id)
    else:
        p = db.scalars(
            select(Program).order_by((Program.status == ProgramStatus.APPROVED).desc(), Program.period_start.desc())
        ).first()
    if not p:
        raise HTTPException(404, "Програму не знайдено")
    return p


def program_measures(db: Session, program: Program) -> list[Measure]:
    return list(
        db.scalars(select(Measure).join(Measure.section).where(Section.program_id == program.id)
            .order_by(Section.number, func.length(Measure.code), Measure.code))
    )


def _status_counts(ms: list[Measure], today: date) -> dict[str, int]:
    c = Counter()
    for m in ms:
        p = m.period_for(today)
        if p:
            c[p.status.value] += 1
    return {st.value: c.get(st.value, 0) for st in MeasureStatus}


def _pct(a: int, b: int) -> float:
    return round(100 * a / b, 1) if b else 0.0


def _calendar(ms: list[Measure], today: date, days: int | None = None) -> list[CalendarItem]:
    out = []
    for m in ms:
        p = m.period_for(today)
        if not p:
            continue
        d = m.deadline_for(p)
        if days is not None and not (today <= d <= today + timedelta(days=days)):
            continue
        out.append(CalendarItem(date=d, measure_id=m.id, code=m.code, title=m.title, status=p.status,
                                is_overdue=m.is_overdue(today)))
    return sorted(out, key=lambda x: x.date)


def _flags_by_type(ms: list[Measure]) -> dict[str, int]:
    c = Counter(f.type.value for m in ms for f in m.flags if f.status == FlagStatus.OPEN)
    return {t.value: c.get(t.value, 0) for t in FlagType}


def rec_out(r: Recommendation) -> s.RecommendationOut:
    return s.RecommendationOut(**{**s.RecommendationOut.model_validate(r).model_dump(),
                                  "measure_title": r.measure.title if r.measure else None})


def reminder_out(r: Reminder) -> s.ReminderOut:
    return s.ReminderOut(id=r.id, measure_id=r.measure_id, measure_title=r.measure.title, send_at=r.send_at,
                         channel=r.channel, text=r.text, sent=r.sent,
                         deliveries=[s.DeliveryOut.model_validate(x) for x in r.deliveries])


def executor(db: Session, user: User, today: date) -> ExecutorDashboard:
    mine = [m for m in db.scalars(select(Measure)) if is_assigned(user, m)
            and m.section.program.status == ProgramStatus.APPROVED]
    upcoming, returned, overdue = [], [], []
    for m in mine:
        p = m.period_for(today)
        if not p:
            continue
        d = m.deadline_for(p)
        if m.is_overdue(today):
            overdue.append(measure_item(m, today))
        elif p.status not in FINAL_STATUSES and d <= today + timedelta(days=30):
            upcoming.append(_with_risk(m, today))
        if p.status == MeasureStatus.RETURNED:
            last = next((a for a in reversed(p.approvals)), None)
            returned.append(ReturnedItem(measure=measure_item(m, today), comment=last.comment if last else ""))
    reminders = db.scalars(
        select(Reminder).where(Reminder.user_id == user.id, Reminder.sent.is_(True)).order_by(Reminder.send_at.desc()).limit(20)
    )
    return ExecutorDashboard(
        upcoming=sorted(upcoming, key=lambda x: x.deadline),
        returned=returned,
        overdue=sorted(overdue, key=lambda x: x.deadline),
        reminders=[reminder_out(r) for r in reminders],
        total_mine=len(mine),
    )


def coordinator(db: Session, program: Program, today: date, see: "Scope | None" = None) -> CoordinatorDashboard:
    ms = program_measures(db, program)
    if see is not None:
        ms = see.measures(ms)
    queue = [measure_item(m, today) for m in ms if (p := m.period_for(today)) and p.status == MeasureStatus.ON_REVIEW]
    sections = []
    for sec in program.sections:
        sm = [m for m in ms if m.section_id == sec.id]
        if see is not None and not see.whole_program and not sm:
            continue
        bs = _status_counts(sm, today)
        sections.append(SectionProgress(number=sec.number, title=sec.title, total=len(sm), by_status=bs,
                                        done_percent=_pct(bs["DONE"], len(sm)),
                                        overdue=sum(m.is_overdue(today) for m in sm)))
    period = halfyear.of(today)
    missing = []
    for m in ms:
        p = m.period_for(today)
        not_due = p is not None and m.deadline_for(p) > halfyear.end(period)
        ready = p is not None and (not_due or p.status in FINAL_STATUSES)
        if not ready:
            missing.append(measure_item(m, today))
    flags = [f for m in ms for f in m.flags if f.status == FlagStatus.OPEN]
    return CoordinatorDashboard(
        program_id=program.id,
        review_queue=queue,
        flags_by_type=_flags_by_type(ms),
        open_flags=[flag_out(f) for f in sorted(flags, key=lambda f: f.created_at, reverse=True)],
        progress_by_section=sections,
        calendar=_calendar(ms, today),
        report_readiness=ReportReadiness(period=period, total=len(ms), ready=len(ms) - len(missing),
                                         percent=_pct(len(ms) - len(missing), len(ms)), missing=missing),
    )


def _units(db: Session, ms: list[Measure], today: date) -> list[UnitCell]:
    by_unit: dict[uuid.UUID, list[Measure]] = {}
    for m in ms:
        r = m.responsible
        if r:
            by_unit.setdefault(r.org_unit_id, []).append(m)
    cells = []
    for uid, items in by_unit.items():
        risks = [non_execution_risk(m, today) for m in items]
        level = max((r.level for r in risks), key=_ORDER.get, default=RiskLevel.LOW)
        n_high = sum(r.level == RiskLevel.HIGH for r in risks)
        n_med = sum(r.level == RiskLevel.MEDIUM for r in risks)
        reasons = []
        if n_high:
            reasons.append(f"Заходів з високим ризиком невиконання: {n_high}")
        if n_med:
            reasons.append(f"Заходів із середнім ризиком: {n_med}")
        cells.append(UnitCell(
            org_unit_id=uid, name=db.get(OrgUnit, uid).name, total=len(items),
            overdue=sum(m.is_overdue(today) for m in items),
            open_flags=sum(1 for m in items for f in m.flags if f.status == FlagStatus.OPEN),
            level=level, reasons=reasons,
        ))
    return sorted(cells, key=lambda c: c.name)


def executive(db: Session, program: Program, today: date, see: "Scope | None" = None) -> ExecutiveDashboard:
    ms = program_measures(db, program)
    if see is not None:
        ms = see.measures(ms)
    bs = _status_counts(ms, today)
    risk_ids = {m.risk_id for m in ms if m.risk_id}
    risks = []
    for r in db.scalars(select(CorruptionRisk).where(CorruptionRisk.id.in_(risk_ids)).order_by(CorruptionRisk.code)):
        rm = [m for m in ms if m.risk_id == r.id]
        inds = [indicator_out(i) for i in r.indicators]
        risks.append(RiskState(
            id=r.id, code=r.code, description=r.description, level=r.level, measures_total=len(rm),
            measures_done=sum(1 for m in rm if (p := m.period_for(today)) and p.status == MeasureStatus.DONE),
            indicators=inds, reduced=bool(inds) and all(i.is_improved for i in inds),
        ))
    critical = [x for m in ms if (x := _with_risk(m, today)).non_execution_risk.level == RiskLevel.HIGH
                or any(f.type in (FlagType.FORMAL_CLOSURE, FlagType.WORSENING) for f in x.open_flags)]
    lvl = {RiskLevel.CRITICAL: 0, RiskLevel.HIGH: 1, RiskLevel.MEDIUM: 2, RiskLevel.LOW: 3}
    critical.sort(key=lambda x: (lvl[x.risk.level] if x.risk else 4, x.deadline))
    recs = db.scalars(select(Recommendation).where(Recommendation.status == RecStatus.PROPOSED))
    recs = sorted(recs, key=lambda r: (r.basis.get("priority", 9), r.created_at))
    return ExecutiveDashboard(
        program_id=program.id,
        overall=Overall(
            total=len(ms), by_status=bs, done_percent=_pct(bs["DONE"], len(ms)),
            overdue=sum(m.is_overdue(today) for m in ms), risks_total=len(risks),
            risks_reduced=sum(r.reduced for r in risks),
            open_flags=sum(1 for m in ms for f in m.flags if f.status == FlagStatus.OPEN),
        ),
        critical=critical,
        risks=risks,
        units=_units(db, ms, today),
        upcoming_deadlines=_calendar(ms, today, days=30),
        recommendations=[rec_out(r) for r in recs if (r.measure is None or r.measure.section.program_id == program.id)
                         and (see is None or see.recommendation(r))],
        flags_by_type=_flags_by_type(ms),
    )


def unit(db: Session, program: Program, org_unit_id: uuid.UUID, today: date) -> UnitDashboard:
    ou = db.get(OrgUnit, org_unit_id)
    if not ou:
        raise HTTPException(404, "Підрозділ не знайдено")
    ms = [m for m in program_measures(db, program) if any(a.org_unit_id == org_unit_id for a in m.assignments)]
    cells = _units(db, [m for m in ms if m.responsible and m.responsible.org_unit_id == org_unit_id], today)
    cell = cells[0] if cells else UnitCell(org_unit_id=ou.id, name=ou.name, total=0, overdue=0, open_flags=0,
                                           level=RiskLevel.LOW, reasons=[])
    return UnitDashboard(org_unit_id=ou.id, name=ou.name, cell=cell, measures=[_with_risk(m, today) for m in ms])
