from datetime import date
from decimal import Decimal

from fastapi import HTTPException, UploadFile, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import audit, halfyear
from ..enums import STATUS_UA, EDITABLE_BY_EXECUTOR, SECTION_TITLES, Decision, MeasureStatus, ProgramStatus
from ..models import (
    Approval,
    CorruptionRisk,
    DeadlineChange,
    Evidence,
    Indicator,
    IndicatorValue,
    Measure,
    MeasureAssignment,
    MeasurePeriod,
    Program,
    ProgressUpdate,
    Section,
    User,
    local_date,
)
from ..schemas import domain as s
from . import integra, storage
from .rules import submit_hints

MEASURE_FIELDS = ("code", "title", "is_permanent", "planned_deadline", "risk_id", "indicator_text", "indicator_id",
                  "required_evidence")
_EXEC_FIELDS = {"indicator_text", "indicator_unit", "indicator_target"}
PERIOD_FIELDS = ("status", "actual_date", "result_description", "non_execution_reason")
MAX_FILE_BYTES = 50 * 1024 * 1024


def _409(msg: str) -> HTTPException:
    return HTTPException(status.HTTP_409_CONFLICT, msg)


def create_program(db: Session, user: User, data: s.ProgramIn) -> Program:
    if data.period_end < data.period_start:
        raise HTTPException(422, "Кінець періоду має бути пізніше за початок")
    p = Program(**data.model_dump())
    p.sections = [Section(number=n, title=t) for n, t in SECTION_TITLES.items()]
    db.add(p)
    db.flush()
    audit.record(db, user, "program", p.id, "create", None, audit.snapshot(p, *data.model_dump().keys()))
    return p


def approve_program(db: Session, user: User, program: Program, today: date) -> Program:
    if program.status != ProgramStatus.DRAFT:
        raise _409("Програму вже затверджено")
    program.status = ProgramStatus.APPROVED
    for sec in program.sections:
        for m in sec.measures:
            for p in m.periods:
                if p.status == MeasureStatus.DRAFT:
                    _transition(db, user, p, MeasureStatus.PLANNED, "Паспорт програми затверджено")
    from .risk_model import freeze_baselines, program_indicators

    freeze_baselines(program_indicators(program))
    audit.record(db, user, "program", program.id, "approve", {"status": "DRAFT"}, {"status": "APPROVED"})
    start_due_periods(db, today)
    return program


def start_due_periods(db: Session, today: date) -> int:
    n = 0
    rows = db.scalars(select(MeasurePeriod).where(MeasurePeriod.status == MeasureStatus.PLANNED))
    for p in rows:
        m = p.measure
        program = m.section.program
        begins = halfyear.start(p.period) if m.is_permanent else program.period_start
        if max(begins, program.period_start) <= today:
            _transition(db, None, p, MeasureStatus.IN_PROGRESS, "Настала дата початку")
            n += 1
    return n


def _sync_periods(m: Measure, program: Program) -> None:
    if m.is_permanent:
        wanted = program.half_years
    else:
        wanted = [halfyear.of(m.planned_deadline)]
    initial = MeasureStatus.DRAFT if program.status == ProgramStatus.DRAFT else MeasureStatus.PLANNED
    have = {p.period for p in m.periods}
    for hy in wanted:
        if hy not in have:
            m.periods.append(MeasurePeriod(period=hy, status=initial))
    for p in list(m.periods):
        if p.period not in wanted and p.status in (MeasureStatus.DRAFT, MeasureStatus.PLANNED) and not p.evidence:
            m.periods.remove(p)


def _set_assignments(m: Measure, items: list[s.AssignmentIn]) -> None:
    if items and sum(a.is_responsible for a in items) == 0:
        items[0].is_responsible = True
    m.assignments = [MeasureAssignment(**a.model_dump()) for a in items]


def _set_execution_indicator(db: Session, m: Measure, text: str, unit: str, target) -> None:
    """Індикатор виконання з паспорта: назва — завжди; кількісний (з ціллю) — власний Indicator заходу
    (самозвіт виконавця, не індикатор ризику), а факти — його значення."""
    m.indicator_text = (text or "").strip()
    if target is None:
        m.indicator = None
        return
    own = m.indicator if m.indicator is not None and m.indicator.risk_id is None else None
    if own is None:
        own = Indicator(name=m.indicator_text or m.title, unit=unit or "", baseline=Decimal(0), target=target,
                        weight=Decimal(1), lag_months=0, source="звіт виконавця", independent=False)
        db.add(own)
        m.indicator = own
    else:
        own.name, own.unit, own.target = m.indicator_text or m.title, unit or "", target


def _check_links(db: Session, program_id, risk_id) -> None:
    if risk_id is not None:
        risk = db.get(CorruptionRisk, risk_id)
        if risk is None:
            raise HTTPException(422, "Корупційний ризик не знайдено")
        if risk.program_id is not None and risk.program_id != program_id:
            raise HTTPException(422, "Корупційний ризик належить іншій програмі")


def create_measure(db: Session, user: User, data: s.MeasureIn) -> Measure:
    section = db.get(Section, data.section_id)
    if not section:
        raise HTTPException(404, "Розділ не знайдено")
    _check_links(db, section.program_id, data.risk_id)
    m = Measure(**data.model_dump(exclude={"assignments"} | _EXEC_FIELDS))
    m.section = section
    _set_execution_indicator(db, m, data.indicator_text, data.indicator_unit, data.indicator_target)
    _set_assignments(m, data.assignments)
    _sync_periods(m, section.program)
    db.add(m)
    db.flush()
    audit.record(db, user, "measure", m.id, "create", None, audit.snapshot(m, *MEASURE_FIELDS))
    return m


def patch_measure(db: Session, user: User, m: Measure, data: s.MeasurePatch) -> Measure:
    old = audit.snapshot(m, *MEASURE_FIELDS)
    changes = data.model_dump(exclude_unset=True, exclude={"assignments"})
    current = {"indicator_unit": m.indicator.unit if m.indicator else "",
               "indicator_target": m.indicator.target if m.indicator else None}
    changed = [k for k, v in changes.items() if (current[k] if k in current else getattr(m, k)) != v]
    if changed and m.section.program.status != ProgramStatus.DRAFT:
        raise _409("Програму затверджено: паспорт заходу змінювати не можна, лише виконавців")
    if "risk_id" in changed:
        _check_links(db, m.section.program_id, changes.get("risk_id", m.risk_id))
    for k, v in changes.items():
        if k not in _EXEC_FIELDS:
            setattr(m, k, v)
    if _EXEC_FIELDS & set(changed):
        _set_execution_indicator(db, m, changes.get("indicator_text", m.indicator_text),
                                 changes.get("indicator_unit", current["indicator_unit"]),
                                 changes.get("indicator_target", current["indicator_target"]))
    if data.assignments is not None:
        old["assignments"] = [str(a.org_unit_id) for a in m.assignments]
        _set_assignments(m, data.assignments)
    _sync_periods(m, m.section.program)
    db.flush()
    new = audit.snapshot(m, *MEASURE_FIELDS)
    if data.assignments is not None:
        new["assignments"] = [str(a.org_unit_id) for a in data.assignments]
    audit.record(db, user, "measure", m.id, "update", old, new)
    return m


def _transition(db: Session, user: User | None, p: MeasurePeriod, to: MeasureStatus, text: str) -> None:
    old = audit.snapshot(p, *PERIOD_FIELDS)
    frm = p.status
    p.status = to
    db.add(ProgressUpdate(measure_period=p, author_id=user.id if user else None, status_from=frm, status_to=to, body=text))
    db.flush()
    audit.record(db, user, "measure_period", p.id, f"status:{frm}->{to}", old, audit.snapshot(p, *PERIOD_FIELDS))
    integra.on_measure_changed(db, p.measure)


def require_period(m: Measure, today: date, period: str | None) -> MeasurePeriod:
    from .mappers import resolve_period

    p = resolve_period(m, today, period)
    if not p:
        raise HTTPException(404, "Звітний період заходу не знайдено")
    return p


def read_files(files: list[UploadFile], doc_types: list[str], doc_dates: list[date],
               today: date) -> list[tuple[str, str, bytes, str, date]]:
    """Файли з типом і датою документа на кожен (словник: pidtverdzhennia.typ, data_dokumenta).
    Дата обовʼязкова: без неї не перевірити підтвердження «заднім числом» (правило R7b)."""
    named = [f for f in files if f.filename]
    if len(doc_types) != len(named) or len(doc_dates) != len(named):
        raise HTTPException(422, "Для кожного файлу вкажіть тип документа і дату документа")
    out = []
    for f, doc_type, doc_date in zip(named, doc_types, doc_dates, strict=True):
        doc_type = doc_type.strip().lower()
        if not doc_type:
            raise HTTPException(422, f"{f.filename}: вкажіть тип документа (наказ, протокол, акт, звіт…)")
        if doc_date > today:
            raise HTTPException(422, f"{f.filename}: дата документа {doc_date:%d.%m.%Y} ще не настала")
        content_type = storage.evidence_type(f.filename)
        if content_type is None:
            allowed = ", ".join(sorted(storage.EVIDENCE_TYPES))
            raise HTTPException(415, f"{f.filename}: такий тип файлу не приймається. Дозволено: {allowed}")
        data = f.file.read(MAX_FILE_BYTES + 1)
        if len(data) > MAX_FILE_BYTES:
            raise HTTPException(413, f"{f.filename}: файл більший за {MAX_FILE_BYTES // (1024 * 1024)} МБ")
        out.append((f.filename, content_type, data, doc_type, doc_date))
    return out


def store_files(db: Session, user: User, p: MeasurePeriod,
                files: list[tuple[str, str, bytes, str, date]]) -> list[Evidence]:
    out = []
    for name, content_type, data, doc_type, doc_date in files:
        key, digest = storage.put_object(db, f"measure-periods/{p.id}", name, data)
        version = (
            db.scalar(
                select(func.count())
                .select_from(Evidence)
                .where(Evidence.measure_period_id == p.id, Evidence.file_name == name)
            )
            or 0
        ) + 1
        e = Evidence(
            measure_period=p,
            uploaded_by=user.id,
            file_name=name,
            content_type=content_type,
            size=len(data),
            object_key=key,
            sha256=digest,
            version=version,
            doc_type=doc_type,
            document_date=doc_date,
        )
        db.add(e)
        db.flush()
        audit.record(
            db, user, "evidence", e.id, "upload", None,
            {"measurePeriodId": str(p.id), "fileName": e.file_name, "sha256": digest, "version": version,
             "docType": doc_type, "documentDate": doc_date.isoformat()},
        )
        out.append(e)
    return out


def postpone(db: Session, user: User, m: Measure, data: s.DeadlineChangeIn, today: date) -> DeadlineChange:
    """Внутрішнє рішення координатора про перенесення строку (словник: perenesennia_strokiv). Строк у затвердженій
    програмі не змінюється: прострочення (R1) і звіт НАЗК рахуються за ним, нагадування — за новим строком."""
    if m.is_permanent:
        raise HTTPException(422, "Постійний захід не має строку, який можна перенести")
    program = m.section.program
    old = m.internal_deadline
    if data.new_deadline == old:
        raise HTTPException(422, f"Новий строк збігається з чинним ({old:%d.%m.%Y})")
    if not program.period_start <= data.new_deadline <= program.period_end:
        raise HTTPException(422, f"Новий строк поза періодом програми ({program.period_start:%d.%m.%Y}–"
                                 f"{program.period_end:%d.%m.%Y})")
    c = DeadlineChange(measure=m, decided_on=today, old_deadline=old, new_deadline=data.new_deadline,
                       reason=data.reason.strip(), decided_by=user.id)
    db.add(c)
    db.flush()
    audit.record(db, user, "measure", m.id, "postpone", {"internalDeadline": old.isoformat()},
                 {"internalDeadline": data.new_deadline.isoformat(), "reason": c.reason,
                  "deadlineChangeId": str(c.id)})
    return c


def add_progress(db: Session, user: User, p: MeasurePeriod, text: str) -> None:
    if p.status not in EDITABLE_BY_EXECUTOR:
        raise _409(f"Захід у статусі «{STATUS_UA[p.status]}»: вносити зміни зараз не можна")
    if p.status == MeasureStatus.PLANNED:
        _transition(db, user, p, MeasureStatus.IN_PROGRESS, text)
    else:
        db.add(ProgressUpdate(measure_period=p, author_id=user.id, status_from=p.status, status_to=p.status, body=text))
        audit.record(db, user, "measure_period", p.id, "progress", None, {"text": text})


def submit(
    db: Session,
    user: User,
    m: Measure,
    p: MeasurePeriod,
    result_description: str | None,
    non_execution_reason: str | None,
    files: list[UploadFile],
    ai_draft_key: str | None = None,
    *,
    doc_types: list[str] = (),
    doc_dates: list[date] = (),
    indicator_value: Decimal | None = None,
    today: date,
) -> list[str]:
    if p.status not in EDITABLE_BY_EXECUTOR:
        raise _409(f"Захід у статусі «{STATUS_UA[p.status]}»: подати результат зараз не можна")
    result_description = (result_description or "").strip() or None
    non_execution_reason = (non_execution_reason or "").strip() or None
    if result_description and non_execution_reason:
        raise HTTPException(422, "Вкажіть або опис результату, або причину невиконання, а не обидва")
    evidence_count = len(p.evidence) + sum(1 for f in files if f.filename)
    if not result_description and not non_execution_reason:
        raise HTTPException(422, "Потрібен опис результату або причина невиконання")
    hints = submit_hints(m.title, result_description, m.required_evidence, evidence_count)
    if result_description and m.required_evidence and evidence_count == 0:
        raise HTTPException(422, {"message": "Не додано обовʼязкові підтвердні матеріали", "hints": hints})
    own = m.indicator if m.indicator is not None and m.indicator.risk_id is None else None
    if indicator_value is not None and indicator_value < 0:
        raise HTTPException(422, "Фактичне значення індикатора не може бути відʼємним")
    if result_description and own is not None and indicator_value is None:
        raise HTTPException(422, f"Вкажіть фактичне значення індикатора виконання «{own.name}» "
                                 f"(ціль {own.target:g} {own.unit})".rstrip() + ".")
    read = read_files(files, list(doc_types), list(doc_dates), today)
    ai_draft: dict[str, object] = {}
    if ai_draft_key:
        from .intake import draft_usage

        text = result_description or non_execution_reason or ""
        ai_draft = draft_usage(db, user, m, ai_draft_key, text, "done" if result_description else "not_done")
    saved = store_files(db, user, p, read)
    if own is not None and indicator_value is not None:
        iv = IndicatorValue(indicator=own, value=indicator_value, measured_at=today,
                            source_evidence_id=saved[0].id if saved else None)
        db.add(iv)
        db.flush()
        audit.record(db, user, "indicator_value", iv.id, "create", None,
                     audit.snapshot(iv, "indicator_id", "value", "measured_at") | {"source": "submit"})

    old = audit.snapshot(p, *PERIOD_FIELDS)
    p.result_description = result_description
    p.non_execution_reason = non_execution_reason
    db.flush()
    audit.record(db, user, "measure_period", p.id, "submit", old, audit.snapshot(p, *PERIOD_FIELDS) | ai_draft)
    _transition(db, user, p, MeasureStatus.ON_REVIEW, result_description or non_execution_reason or "")
    return hints


def _ensure_not_own(user: User, p: MeasurePeriod) -> None:
    submitters = {u.author_id for u in p.updates if u.status_to == MeasureStatus.ON_REVIEW}
    if user.id in submitters:
        raise HTTPException(403, "Не можна розглядати власний поданий результат")


def approve(db: Session, user: User, m: Measure, p: MeasurePeriod, data: s.ApproveIn, today: date) -> None:
    if p.status != MeasureStatus.ON_REVIEW:
        raise _409(f"Захід у статусі «{STATUS_UA[p.status]}», а розглядати можна лише «На перевірці»")
    _ensure_not_own(user, p)
    if data.indicator_value:
        if not m.indicator:
            raise HTTPException(422, "У заходу немає індикатора")
        iv = IndicatorValue(indicator=m.indicator, **data.indicator_value.model_dump())
        db.add(iv)
        db.flush()
        audit.record(db, user, "indicator_value", iv.id, "create", None, audit.snapshot(iv, "indicator_id", "value", "measured_at"))
    db.add(Approval(measure_period=p, reviewer_id=user.id, decision=Decision.APPROVED, comment=data.comment))
    to = MeasureStatus.DONE if p.result_description else MeasureStatus.NOT_DONE
    # Фактичний строк — коли виконавець подав результат (словник: fakt_data), а не коли координатор погодив:
    # інакше затримка перевірки виглядала б як запізнення виконавця (R7a, «Фактичний строк» у звіті НАЗК).
    submitted = [u.created_at for u in p.updates if u.status_to == MeasureStatus.ON_REVIEW]
    p.actual_date = p.actual_date or (local_date(submitted[-1]) if submitted else today)
    _transition(db, user, p, to, data.comment or "Погоджено координатором")


def return_for_rework(db: Session, user: User, p: MeasurePeriod, comment: str) -> None:
    if p.status != MeasureStatus.ON_REVIEW:
        raise _409(f"Захід у статусі «{STATUS_UA[p.status]}», а розглядати можна лише «На перевірці»")
    _ensure_not_own(user, p)
    db.add(Approval(measure_period=p, reviewer_id=user.id, decision=Decision.RETURNED, comment=comment))
    _transition(db, user, p, MeasureStatus.RETURNED, comment)


def close_ended_periods(db: Session, today: date) -> int:
    n = 0
    open_statuses = (MeasureStatus.PLANNED, MeasureStatus.IN_PROGRESS, MeasureStatus.RETURNED)
    for p in db.scalars(select(MeasurePeriod).where(MeasurePeriod.status.in_(open_statuses))):
        if halfyear.end(p.period) < today and p.measure.section.program.status == ProgramStatus.APPROVED:
            p.non_execution_reason = p.non_execution_reason or "Звітний період завершився без погодженого результату"
            _transition(db, None, p, MeasureStatus.NOT_DONE, p.non_execution_reason)
            n += 1
    return n
