import uuid
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import halfyear
from ..config import settings
from ..enums import FINAL_STATUSES, FLAG_UA, Decision, FlagStatus, FlagType, MeasureStatus, RecStatus, Role
from ..models import Evidence, Measure, MeasurePeriod, OrgUnit, Program, Recommendation, User, as_utc, local_date
from ..schemas import performance as s
from .analytics import risk_dynamics
from .dashboards import program_measures
from .risk_model import completed_on

UPCOMING_DAYS = 30
STALE_REVIEW_DAYS = 7
# Частка прострочених серед заходів, строк яких настав: до 15 % — «окремі відставання», далі — «відстає».
BEHIND_SHARE = 0.15

NO_UNIT = "Без відповідального підрозділу"
SHORT_SECTIONS = {1: "Загальна політика", 2: "Усунення корупційних ризиків", 3: "Навчання та інформування"}


def _pct(x: int, total: int) -> float:
    return round(100 * x / total, 1) if total else 0.0


def _plural(n: int, one: str, few: str, many: str) -> str:
    if n % 10 == 1 and n % 100 != 11:
        return one
    if 2 <= n % 10 <= 4 and not 12 <= n % 100 <= 14:
        return few
    return many


def _measures(n: int) -> str:
    return f"{n} {_plural(n, 'захід', 'заходи', 'заходів')}"


def unit_subtree(db: Session, unit_id: uuid.UUID) -> set[uuid.UUID]:
    children: dict[uuid.UUID | None, list[uuid.UUID]] = {}
    for u in db.scalars(select(OrgUnit)):
        children.setdefault(u.parent_id, []).append(u.id)
    out: set[uuid.UUID] = set()
    stack = [unit_id]
    while stack:
        uid = stack.pop()
        if uid not in out:
            out.add(uid)
            stack.extend(children.get(uid, []))
    return out


def _unit_of(m: Measure) -> OrgUnit | None:
    a = m.responsible or (m.assignments[0] if m.assignments else None)
    return a.org_unit if a else None


def summary(db: Session, program: Program, today: date, scope: set[uuid.UUID] | None = None,
            scope_name: str | None = None) -> s.AnalyticsSummary:
    ms = program_measures(db, program)
    if scope is not None:
        ms = [m for m in ms if (u := _unit_of(m)) and u.id in scope]
    rows = [(m, p) for m in ms if (p := m.period_for(today)) and p.status != MeasureStatus.DRAFT]
    by = {st: sum(1 for _, p in rows if p.status == st) for st in MeasureStatus}
    overdue = [(m, p) for m, p in rows if p.status not in FINAL_STATUSES and m.deadline_for(p) < today]
    due = [(m, p) for m, p in rows if m.deadline_for(p) <= today]
    done_due = sum(1 for _, p in due if p.status == MeasureStatus.DONE)
    dated = [(p, d) for m in ms for p in m.periods if p.status == MeasureStatus.DONE and (d := completed_on(p))]
    on_time = sum(1 for p, d in dated if d <= p.measure.deadline_for(p))

    share = len(overdue) / len(due) if due else 0.0
    if not overdue:
        verdict = s.Verdict(level="good", title="Програма виконується вчасно",
                            text=f"Строк настав для {_measures(len(due))}, виконано {done_due}. Прострочених немає.")
    elif share < BEHIND_SHARE:
        verdict = s.Verdict(level="attention", title="Є окремі відставання",
                            text=f"Строк настав для {_measures(len(due))}, виконано {done_due}, "
                                 f"прострочено {len(overdue)}.")
    else:
        verdict = s.Verdict(level="behind", title="Програма відстає від графіка",
                            text=f"Прострочено {len(overdue)} з {len(due)} заходів, строк яких уже настав "
                                 f"({_pct(len(overdue), len(due)):.0f} %).")

    sections = []
    for sec in program.sections:
        sr = [(m, p) for m, p in rows if m.section_id == sec.id]
        done = sum(1 for _, p in sr if p.status == MeasureStatus.DONE)
        sections.append(s.SummarySection(
            number=sec.number, title=SHORT_SECTIONS.get(sec.number, sec.title), total=len(sr), done=done,
            overdue=sum(1 for m, p in sr if (m, p) in overdue), percent=_pct(done, len(sr))))

    soon = sorted(
        ((m, p, m.deadline_for(p)) for m, p in rows if p.status not in FINAL_STATUSES
         and today <= m.deadline_for(p) <= today + timedelta(days=UPCOMING_DAYS)),
        key=lambda x: x[2],
    )
    upcoming = [s.SummaryDeadline(measure_id=m.id, code=m.code, title=m.title, deadline=d, days_left=(d - today).days,
                                  unit=u.name if (u := _unit_of(m)) else None) for m, p, d in soon[:5]]

    attention: list[str] = []
    if overdue:
        attention.append(f"Прострочено {_measures(len(overdue))}: строк минув, а результат не погоджено.")
    if by[MeasureStatus.RETURNED]:
        n = by[MeasureStatus.RETURNED]
        attention.append(f"{_measures(n)} повернуто на доопрацювання: "
                         f"{_plural(n, 'чекає', 'чекають', 'чекають')} виправлення.")
    stale = 0
    for _, p in rows:
        if p.status == MeasureStatus.ON_REVIEW:
            sent = [u.created_at for u in p.updates if u.status_to == MeasureStatus.ON_REVIEW]
            if sent and (today - local_date(max(sent))).days > STALE_REVIEW_DAYS:
                stale += 1
    if stale:
        attention.append(f"{_measures(stale)} {_plural(stale, 'чекає', 'чекають', 'чекають')} перевірки "
                         f"понад {STALE_REVIEW_DAYS} днів.")
    no_effect = sum(1 for m in ms for f in m.flags if f.status == FlagStatus.OPEN
                    and f.type in (FlagType.FORMAL_CLOSURE, FlagType.WORSENING))
    if no_effect:
        attention.append(f"{_measures(no_effect)} виконано, але зменшення ризику поки не підтверджено даними.")
    mids = {m.id for m in ms}
    proposed = sum(1 for r in db.scalars(select(Recommendation).where(Recommendation.status == RecStatus.PROPOSED))
                   if r.measure_id in mids)
    if proposed:
        attention.append(f"{proposed} {_plural(proposed, 'рекомендація чекає', 'рекомендації чекають', 'рекомендацій чекають')} "
                         f"рішення керівника.")
    if not attention:
        attention.append("Усе за планом: прострочених, повернених і завислих на перевірці заходів немає.")

    risks = risk_dynamics(db, ms, today)
    return s.AnalyticsSummary(
        program_id=program.id, program_title=program.title, period=halfyear.of(today), as_of=today, scope=scope_name,
        total=len(rows), done=by[MeasureStatus.DONE],
        in_work=by[MeasureStatus.PLANNED] + by[MeasureStatus.IN_PROGRESS] + by[MeasureStatus.RETURNED],
        on_review=by[MeasureStatus.ON_REVIEW], overdue=len(overdue), not_done=by[MeasureStatus.NOT_DONE],
        due=len(due), done_percent=_pct(by[MeasureStatus.DONE], len(rows)),
        on_time_percent=_pct(on_time, len(dated)), risks_total=len(risks),
        risks_reduced=sum(r.reduced for r in risks), verdict=verdict, sections=sections, upcoming=upcoming,
        upcoming_total=len(soon), attention=attention,
    )


@dataclass
class Task:
    measure: Measure
    period: MeasurePeriod
    unit: OrgUnit | None
    row: s.TaskRow
    events: list[s.TaskEvent] = field(default_factory=list)
    evidence: list[Evidence] = field(default_factory=list)
    first_pass: bool = False
    reviewed: bool = False  # завершено через рішення координатора


def _name(u: User | None) -> str | None:
    return u.display_name if u else None


def _task(m: Measure, p: MeasurePeriod, today: date, users: dict[uuid.UUID, User]) -> Task:
    deadline = m.deadline_for(p)
    unit = _unit_of(m)
    final = p.status in FINAL_STATUSES
    overdue = not final and deadline < today
    delay = None
    on_time = None
    actual = completed_on(p) if p.status in FINAL_STATUSES else None
    if p.status == MeasureStatus.DONE and actual:
        on_time = actual <= deadline
        delay = max(0, (actual - deadline).days)
    elif overdue:
        delay = (today - deadline).days

    base = dict(measure_id=m.id, code=m.code, title=m.title, period=p.period,
                org_unit_id=unit.id if unit else None, org_unit=unit.name if unit else None)
    submissions = sorted((u for u in p.updates if u.status_to == MeasureStatus.ON_REVIEW), key=lambda u: u.created_at)
    events: list[s.TaskEvent] = []
    for u in submissions:
        events.append(s.TaskEvent(kind="submitted", at=as_utc(u.created_at), actor_id=u.author_id,
                                  actor=_name(users.get(u.author_id)) if u.author_id else None,
                                  executor_id=u.author_id, executor=_name(users.get(u.author_id)) if u.author_id else None,
                                  comment=u.body or "", **base))
    returns = 0
    approvals = sorted(p.approvals, key=lambda a: a.created_at)
    for ap in approvals:
        before = [u for u in submissions if u.created_at <= ap.created_at]
        executor = before[-1].author_id if before else None
        returned = ap.decision == Decision.RETURNED
        if returned:
            returns += 1
        events.append(s.TaskEvent(
            kind="returned" if returned else "approved", at=as_utc(ap.created_at), actor_id=ap.reviewer_id,
            actor=_name(users.get(ap.reviewer_id)) if ap.reviewer_id else None, executor_id=executor,
            executor=_name(users.get(executor)) if executor else None, comment=ap.comment or "",
            round=returns if returned else None, **base))
    approved_at = [ap.created_at for ap in approvals if ap.decision == Decision.APPROVED]
    for e in events:
        if e.kind == "returned":
            e.resolved = any(as_utc(a) > e.at for a in approved_at)

    executor_ids: list[uuid.UUID] = []
    for u in submissions:
        if u.author_id and u.author_id not in executor_ids:
            executor_ids.append(u.author_id)
    if not executor_ids:
        executor_ids = [a.user_id for a in m.assignments if a.user_id and a.user_id in users]

    flags = [f.type.value for f in m.flags if f.status == FlagStatus.OPEN
             and (f.facts or {}).get("period", m.period_for(today).period if m.period_for(today) else None) == p.period]
    activity = [e.at for e in events] + [as_utc(x.uploaded_at) for x in p.evidence]
    row = s.TaskRow(
        measure_id=m.id, period_id=p.id, code=m.code, title=m.title, section=m.section.number, period=p.period,
        status=p.status, deadline=deadline, actual_date=actual, delay_days=delay, on_time=on_time,
        overdue=overdue, org_unit_id=base["org_unit_id"], org_unit=base["org_unit"],
        executors=[users[i].display_name for i in executor_ids if i in users], executor_ids=executor_ids,
        submissions=len(submissions), returns=returns, evidence=len(p.evidence), open_flags=flags,
        risk_code=m.risk.code if m.risk else None, last_activity=max(activity) if activity else None,
    )
    reviewed = final and bool(approved_at)
    return Task(m, p, unit, row, events, list(p.evidence), first_pass=reviewed and returns == 0, reviewed=reviewed)


def _counters(cls: type, tasks: list[Task], events: Iterable[s.TaskEvent], evidence: int, **extra) -> s.Counters:
    c = cls(**extra)
    reviewed = 0
    for t in tasks:
        r, st = t.row, t.period.status
        c.tasks += 1
        if st == MeasureStatus.DONE:
            c.done += 1
            if r.on_time is True:
                c.on_time += 1
            elif r.on_time is False:
                c.late_done += 1
        elif st == MeasureStatus.NOT_DONE:
            c.not_done += 1
        elif st == MeasureStatus.PARTIAL:
            c.partial += 1
        elif st == MeasureStatus.ON_REVIEW:
            c.on_review += 1
        else:
            c.in_work += 1
        c.overdue += r.overdue
        if r.delay_days:
            c.delayed += 1
            c.delay_days_total += r.delay_days
        c.open_flags += len(r.open_flags)
        reviewed += t.reviewed
        c.first_pass += t.first_pass
    for e in events:
        if e.kind == "submitted":
            c.submissions += 1
        else:
            c.decisions += 1
            c.returns += e.kind == "returned"
    c.evidence = evidence
    c.done_percent = _pct(c.done, c.tasks)
    c.on_time_percent = _pct(c.on_time, c.on_time + c.late_done)  # серед виконаних з відомою датою
    c.return_rate = _pct(c.returns, c.decisions)
    c.first_pass_percent = _pct(c.first_pass, reviewed)
    c.avg_delay_days = round(c.delay_days_total / c.delayed, 1) if c.delayed else None
    return c


def _review_days(events: list[s.TaskEvent], all_events: list[s.TaskEvent]) -> float | None:
    spans = []
    for e in events:
        sent = [x.at for x in all_events if x.kind == "submitted" and x.measure_id == e.measure_id
                and x.period == e.period and x.at <= e.at]
        if sent:
            spans.append((e.at - max(sent)).total_seconds() / 86400)
    return round(sum(spans) / len(spans), 1) if spans else None


def report(db: Session, program: Program, today: date, period: str | None = None,
           org_unit_id: uuid.UUID | None = None, user_id: uuid.UUID | None = None,
           scope: set[uuid.UUID] | None = None, scope_name: str | None = None) -> s.PerformanceReport:
    ms = program_measures(db, program)
    users = {u.id: u for u in db.scalars(select(User))}
    periods = sorted({p.period for m in ms for p in m.periods
                      if p.status != MeasureStatus.DRAFT and halfyear.start(p.period) <= today})

    def in_scope(p: MeasurePeriod) -> bool:
        if p.status == MeasureStatus.DRAFT:
            return False
        return p.period == period if period else halfyear.start(p.period) <= today

    tasks = [_task(m, p, today, users) for m in ms for p in m.periods if in_scope(p)]
    if scope is not None:
        tasks = [t for t in tasks if t.row.org_unit_id in scope]
        periods = sorted({t.row.period for t in tasks} | ({period} if period else set()))
    if org_unit_id:
        tasks = [t for t in tasks if t.unit and t.unit.id == org_unit_id]
    if user_id:
        tasks = [t for t in tasks if user_id in t.row.executor_ids]
    events = sorted((e for t in tasks for e in t.events), key=lambda e: e.at, reverse=True)

    units = []
    for uid in {t.row.org_unit_id for t in tasks}:
        ut = [t for t in tasks if t.row.org_unit_id == uid]
        people = {i for t in ut for i in t.row.executor_ids} | {
            u.id for u in users.values() if uid and u.org_unit_id == uid and u.role == Role.EXECUTOR and not u.deleted_at}
        units.append(_counters(s.UnitPerformance, ut, (e for t in ut for e in t.events),
                               sum(len(t.evidence) for t in ut), org_unit_id=uid,
                               name=ut[0].row.org_unit or NO_UNIT, people=len(people)))
    units.sort(key=lambda u: (u.org_unit_id is None, u.name))

    ids = {i for t in tasks for i in t.row.executor_ids}
    if not user_id:
        unit_ids = {t.unit.id for t in tasks if t.unit}
        ids |= {u.id for u in users.values() if u.role == Role.EXECUTOR and not u.deleted_at and u.org_unit_id in unit_ids}
    if scope is not None:
        ids = {i for i in ids if users[i].org_unit_id in scope}
    people = []
    for pid in ids:
        u = users[pid]
        pt = [t for t in tasks if pid in t.row.executor_ids]
        mine = [e for t in tasks for e in t.events if e.executor_id == pid]
        uploads = [x for t in tasks for x in t.evidence if x.uploaded_by == pid]
        acted = [e.at for t in tasks for e in t.events if e.actor_id == pid] + [as_utc(x.uploaded_at) for x in uploads]
        people.append(_counters(s.PersonPerformance, pt, mine, len(uploads), user_id=pid, name=u.display_name,
                                role=u.role, org_unit_id=u.org_unit_id, org_unit=u.org_unit.name,
                                active=u.deleted_at is None, last_activity=max(acted) if acted else None))
    people.sort(key=lambda p: (p.org_unit, p.name))

    reviewers = []
    decisions = [e for e in events if e.kind != "submitted"]
    for rid in {e.actor_id for e in decisions
                if e.actor_id and (scope is None or users[e.actor_id].org_unit_id in scope)}:
        mine = [e for e in decisions if e.actor_id == rid]
        returned = sum(e.kind == "returned" for e in mine)
        reviewers.append(s.ReviewerPerformance(
            user_id=rid, name=users[rid].display_name, reviews=len(mine), approved=len(mine) - returned,
            returned=returned, return_rate=_pct(returned, len(mine)), avg_review_days=_review_days(mine, events)))
    reviewers.sort(key=lambda r: r.name)

    return s.PerformanceReport(
        program_id=program.id, program_title=program.title, as_of=today, period=period, periods=periods,
        org_unit_id=org_unit_id, user_id=user_id, scope=scope_name,
        totals=_counters(s.Counters, tasks, events, sum(len(t.evidence) for t in tasks)),
        units=units, people=people, reviewers=reviewers,
        tasks=sorted((t.row for t in tasks), key=lambda r: (r.section, len(r.code), r.code, r.period)),
        events=events,
    )


def _peer_stats(name: str, org_unit: str, shared: int, c: s.Counters) -> s.PeerStats:
    closed = c.done + c.not_done + c.partial
    return s.PeerStats(
        name=name, org_unit=org_unit, shared_measures=shared, tasks=c.tasks, done=c.done, overdue=c.overdue,
        returns=c.returns, done_percent=c.done_percent if c.tasks else None,
        on_time_percent=c.on_time_percent if c.on_time + c.late_done else None,
        return_rate=c.return_rate if c.decisions else None,
        first_pass_percent=c.first_pass_percent if closed else None, avg_delay_days=c.avg_delay_days,
    )


def _avg(values: list) -> float | None:
    known = [v for v in values if v is not None]
    return round(sum(known) / len(known), 1) if known else None


PEER_MIN_GROUP = 3  # менше — середнє розкриває показники конкретних колег


def peers(db: Session, program: Program, today: date, me: User) -> s.PeerReport:
    from ..auth import is_assigned

    ms = program_measures(db, program)
    users = {u.id: u for u in db.scalars(select(User))}
    executors = [u for u in users.values() if u.role == Role.EXECUTOR and not u.deleted_at]

    def members(m: Measure) -> set[uuid.UUID]:
        out: set[uuid.UUID] = set()
        for a in m.assignments:
            if a.user_id:
                u = users.get(a.user_id)
                if u and u.role == Role.EXECUTOR and not u.deleted_at:
                    out.add(u.id)
            else:
                out |= {u.id for u in executors if u.org_unit_id == a.org_unit_id}
        return out

    mine = [m for m in ms if is_assigned(me, m)]
    shared: dict[uuid.UUID, int] = {}
    with_peers = 0
    for m in mine:
        others = members(m) - {me.id}
        with_peers += bool(others)
        for uid in others:
            shared[uid] = shared.get(uid, 0) + 1

    tasks = [_task(m, p, today, users) for m in ms for p in m.periods
             if p.status != MeasureStatus.DRAFT and halfyear.start(p.period) <= today]

    def counters(uid: uuid.UUID) -> s.Counters:
        own = [t for t in tasks if uid in t.row.executor_ids]
        return _counters(s.Counters, own, (e for t in tasks for e in t.events if e.executor_id == uid), 0)

    rows = sorted((_peer_stats(users[uid].display_name, users[uid].org_unit.name, n, counters(uid))
                   for uid, n in shared.items()), key=lambda p: (-p.shared_measures, p.name))
    known = [p for p in rows if p.tasks]
    average = None
    if len(known) >= PEER_MIN_GROUP:
        average = s.PeerStats(
            name="Колеги в середньому", org_unit="", shared_measures=0,
            tasks=round(sum(p.tasks for p in known) / len(known)),
            done=round(sum(p.done for p in known) / len(known)),
            overdue=round(sum(p.overdue for p in known) / len(known)),
            returns=round(sum(p.returns for p in known) / len(known)),
            done_percent=_avg([p.done_percent for p in known]),
            on_time_percent=_avg([p.on_time_percent for p in known]),
            return_rate=_avg([p.return_rate for p in known]),
            first_pass_percent=_avg([p.first_pass_percent for p in known]),
            avg_delay_days=_avg([p.avg_delay_days for p in known]),
        )
    return s.PeerReport(
        program_title=program.title, as_of=today, shared_measures=with_peers,
        me=_peer_stats(me.display_name, me.org_unit.name, len(mine), counters(me.id)), average=average,
        colleagues=len(known), min_group=PEER_MIN_GROUP,
    )


STATUS_UA_SHORT = {
    "DRAFT": "Чернетка", "PLANNED": "Заплановано", "IN_PROGRESS": "В роботі", "ON_REVIEW": "На перевірці",
    "RETURNED": "Повернено", "DONE": "Виконано", "PARTIAL": "Частково", "NOT_DONE": "Не виконано",
}
_COUNTER_HEAD = ["Завдань", "Виконано", "Вчасно, %", "Із запізненням", "Прострочено", "Не виконано", "Подань",
                 "Повернень", "Частка повернень, %", "Без повернень, %", "Сер. запізнення, дн.", "Документів",
                 "Risk Flags"]


def _counter_cells(c: s.Counters) -> list:
    return [c.tasks, c.done, c.on_time_percent, c.late_done, c.overdue, c.not_done, c.submissions, c.returns,
            c.return_rate, c.first_pass_percent, c.avg_delay_days, c.evidence, c.open_flags]


def _dt(x: datetime | None) -> str:
    return as_utc(x).astimezone(settings.tz).strftime("%d.%m.%Y %H:%M") if x else ""


def export_tables(r: s.PerformanceReport) -> dict[str, list[list]]:
    kinds = {"submitted": "Подано на перевірку", "approved": "Погоджено", "returned": "Повернено"}
    return {
        "Підрозділи": [["Підрозділ", "Виконавців", *_COUNTER_HEAD]]
        + [[u.name, u.people, *_counter_cells(u)] for u in r.units],
        "Виконавці": [["Виконавець", "Підрозділ", "Остання дія", *_COUNTER_HEAD]]
        + [[p.name + ("" if p.active else " (видалено)"), p.org_unit, _dt(p.last_activity), *_counter_cells(p)]
           for p in r.people],
        "Перевіряючі": [["Перевіряючий", "Рішень", "Погоджено", "Повернено", "Частка повернень, %",
                         "Сер. час перевірки, дн."]]
        + [[x.name, x.reviews, x.approved, x.returned, x.return_rate, x.avg_review_days] for x in r.reviewers],
        "Завдання": [["Номер", "Захід", "Розділ", "Півріччя", "Статус", "Строк", "Фактично", "Запізнення, дн.",
                      "Підрозділ", "Виконавці", "Подань", "Повернень", "Документів", "Risk Flags", "Ризик"]]
        + [[t.code, t.title, t.section, t.period, STATUS_UA_SHORT[t.status.value], t.deadline.strftime("%d.%m.%Y"),
            t.actual_date.strftime("%d.%m.%Y") if t.actual_date else "", t.delay_days, t.org_unit or "",
            ", ".join(t.executors), t.submissions, t.returns, t.evidence, ", ".join(FLAG_UA.get(x, x) for x in t.open_flags), t.risk_code or ""]
           for t in r.tasks],
        "Хронологія": [["Дата", "Подія", "Номер", "Захід", "Півріччя", "Підрозділ", "Виконавець", "Хто", "Коментар",
                        "Повернення №", "Згодом погоджено"]]
        + [[_dt(e.at), kinds[e.kind], e.code, e.title, e.period, e.org_unit or "", e.executor or "", e.actor or "",
            e.comment, e.round, "" if e.resolved is None else ("так" if e.resolved else "ні")] for e in r.events],
    }

