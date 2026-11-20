import uuid
from datetime import date
from decimal import Decimal
from typing import Annotated
from urllib.parse import quote

from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import Response
from sqlalchemy import func, or_, select
from sqlalchemy.orm import contains_eager, selectinload

from ..auth import Admin, Coordinator, DbDep, UserDep, ensure_can_execute, is_assigned
from ..config import today
from ..enums import EDITABLE_BY_EXECUTOR, STATUS_UA, MeasureStatus, Role
from ..models import AuditLogEntry, Evidence, Measure, MeasureAssignment, MeasurePeriod, Section
from ..schemas import domain as s
from ..services import control, measures as svc, scope, storage
from ..services.mappers import evidence_out, measure_detail, measure_item
from .audit import entry_out

router = APIRouter(prefix="/measures", tags=["Measures & Activity"])


def get_measure(db, measure_id: uuid.UUID) -> Measure:
    m = db.get(Measure, measure_id)
    if not m:
        raise HTTPException(404, "Захід не знайдено")
    return m


def _visible(db, user, m: Measure) -> None:
    if user.role == Role.EXECUTOR and not is_assigned(user, m):
        raise HTTPException(403, "Це не ваш захід")
    scope.of(db, user).ensure_measure(m)


def _detail(db, m: Measure, user, period: str | None = None) -> s.MeasureDetail:
    db.refresh(m)
    return measure_detail(m, today(), user, is_assigned(user, m), period)


@router.get("", response_model=list[s.MeasureListItem])
def list_measures(
    db: DbDep,
    user: UserDep,
    mine: bool = False,
    program_id: Annotated[uuid.UUID | None, Query(alias="programId")] = None,
    section_id: Annotated[uuid.UUID | None, Query(alias="sectionId")] = None,
    org_unit_id: Annotated[uuid.UUID | None, Query(alias="orgUnitId")] = None,
    risk_id: Annotated[uuid.UUID | None, Query(alias="riskId")] = None,
    status: MeasureStatus | None = None,
    overdue: bool | None = None,
    q: str | None = None,
):
    """`?mine=true` — лише власні заходи (для виконавця застосовується завжди)."""
    stmt = (
        select(Measure)
        .join(Measure.section)
        .options(
            contains_eager(Measure.section),
            selectinload(Measure.periods).selectinload(MeasurePeriod.evidence),
            selectinload(Measure.assignments).selectinload(MeasureAssignment.org_unit),
            selectinload(Measure.assignments).selectinload(MeasureAssignment.user),
            selectinload(Measure.flags),
            selectinload(Measure.risk),
        )
    )
    if program_id:
        stmt = stmt.where(Section.program_id == program_id)
    if section_id:
        stmt = stmt.where(Measure.section_id == section_id)
    if risk_id:
        stmt = stmt.where(Measure.risk_id == risk_id)
    if q:
        like = "%" + q.replace("\\", "\\\\").replace("%", r"\%").replace("_", r"\_") + "%"
        stmt = stmt.where(or_(Measure.title.ilike(like, escape="\\"), Measure.code.ilike(like, escape="\\")))
    t = today()
    see = scope.of(db, user)
    out = []
    for m in db.scalars(stmt.order_by(Section.number, func.length(Measure.code), Measure.code)):
        if (mine and not is_assigned(user, m)) or not see.measure(m):
            continue
        if org_unit_id and not any(a.org_unit_id == org_unit_id for a in m.assignments):
            continue
        item = measure_item(m, t)
        if status and item.status != status:
            continue
        if overdue is not None and item.is_overdue != overdue:
            continue
        out.append(item)
    return out


@router.post("", response_model=s.MeasureDetail, status_code=201)
def create_measure(data: s.MeasureIn, db: DbDep, user: Coordinator):
    m = svc.create_measure(db, user, data)
    db.commit()
    return _detail(db, m, user)


@router.get("/{measure_id}", response_model=s.MeasureDetail)
def get_one(measure_id: uuid.UUID, db: DbDep, user: UserDep, period: str | None = None):
    m = get_measure(db, measure_id)
    _visible(db, user, m)
    return measure_detail(m, today(), user, is_assigned(user, m), period)


@router.patch("/{measure_id}", response_model=s.MeasureDetail)
def patch_measure(measure_id: uuid.UUID, data: s.MeasurePatch, db: DbDep, user: Coordinator):
    m = svc.patch_measure(db, user, get_measure(db, measure_id), data)
    control.after_change(db, m, today())
    db.commit()
    return _detail(db, m, user)


@router.post("/{measure_id}/progress", response_model=s.MeasureDetail)
def add_progress(measure_id: uuid.UUID, data: s.ProgressIn, db: DbDep, user: UserDep):
    """Проміжний результат (PLANNED → IN_PROGRESS при першому внесенні)."""
    m = get_measure(db, measure_id)
    ensure_can_execute(user, m)
    svc.add_progress(db, user, svc.require_period(m, today(), data.period), data.text)
    db.commit()
    return _detail(db, m, user, data.period)


@router.post("/{measure_id}/submit", response_model=s.SubmitResult)
def submit(
    measure_id: uuid.UUID,
    db: DbDep,
    user: UserDep,
    result_description: Annotated[str | None, Form(alias="resultDescription")] = None,
    non_execution_reason: Annotated[str | None, Form(alias="nonExecutionReason")] = None,
    period: Annotated[str | None, Form()] = None,
    files: Annotated[list[UploadFile], File()] = [],  # noqa: B006
    ai_draft_key: Annotated[str | None, Form(alias="aiDraftKey")] = None,
    document_types: Annotated[list[str], Form(alias="documentTypes")] = [],  # noqa: B006
    document_dates: Annotated[list[date], Form(alias="documentDates")] = [],  # noqa: B006
    indicator_value: Annotated[Decimal | None, Form(alias="indicatorValue")] = None,
):
    """Внесення за один крок: опис результату (або причини невиконання) + файли з типом і датою документа
    + фактичне значення індикатора виконання (якщо він кількісний) → «На перевірці»."""
    m = get_measure(db, measure_id)
    ensure_can_execute(user, m)
    p = svc.require_period(m, today(), period)
    hints = svc.submit(db, user, m, p, result_description, non_execution_reason, files, ai_draft_key,
                       doc_types=document_types, doc_dates=document_dates, indicator_value=indicator_value,
                       today=today())
    control.after_change(db, m, today())
    db.commit()
    return s.SubmitResult(measure=_detail(db, m, user, p.period), hints=hints)


@router.post("/{measure_id}/deadline-changes", response_model=s.MeasureDetail, status_code=201)
def postpone(measure_id: uuid.UUID, data: s.DeadlineChangeIn, db: DbDep, user: Coordinator):
    """Перенести внутрішній строк заходу (лише координатор, з причиною). Строк у програмі не змінюється;
    два і більше перенесень дають прапорець R6a."""
    m = get_measure(db, measure_id)
    svc.postpone(db, user, m, data, today())
    control.after_change(db, m, today())
    db.commit()
    db.refresh(m)
    return _detail(db, m, user, None)


@router.post("/{measure_id}/approve", response_model=s.MeasureDetail)
def approve(measure_id: uuid.UUID, data: s.ApproveIn, db: DbDep, user: Coordinator):
    m = get_measure(db, measure_id)
    p = svc.require_period(m, today(), data.period)
    svc.approve(db, user, m, p, data, today())
    control.after_change(db, m, today())
    db.commit()
    return _detail(db, m, user, p.period)


@router.post("/{measure_id}/return", response_model=s.MeasureDetail)
def return_for_rework(measure_id: uuid.UUID, data: s.ReturnIn, db: DbDep, user: Coordinator):
    m = get_measure(db, measure_id)
    p = svc.require_period(m, today(), data.period)
    svc.return_for_rework(db, user, p, data.comment)
    control.after_change(db, m, today())
    db.commit()
    return _detail(db, m, user, p.period)


@router.get("/{measure_id}/evidence", response_model=list[s.EvidenceOut])
def list_evidence(measure_id: uuid.UUID, db: DbDep, user: UserDep):
    m = get_measure(db, measure_id)
    _visible(db, user, m)
    return [evidence_out(e, p.period) for p in m.periods for e in p.evidence]


@router.post("/{measure_id}/evidence", response_model=list[s.EvidenceOut], status_code=201)
def upload_evidence(
    measure_id: uuid.UUID,
    db: DbDep,
    user: UserDep,
    files: Annotated[list[UploadFile], File()],
    period: Annotated[str | None, Form()] = None,
    document_types: Annotated[list[str], Form(alias="documentTypes")] = [],  # noqa: B006
    document_dates: Annotated[list[date], Form(alias="documentDates")] = [],  # noqa: B006
):
    m = get_measure(db, measure_id)
    ensure_can_execute(user, m)
    p = svc.require_period(m, today(), period)
    if p.status not in EDITABLE_BY_EXECUTOR:
        raise HTTPException(409, f"Не можна додати матеріали, поки захід у статусі «{STATUS_UA[p.status]}»")
    saved = svc.store_files(db, user, p, svc.read_files(files, document_types, document_dates, today()))
    control.after_change(db, m, today())
    db.commit()
    return [evidence_out(e, p.period) for e in saved]


@router.get("/{measure_id}/evidence/{evidence_id}/download")
def download_evidence(measure_id: uuid.UUID, evidence_id: uuid.UUID, db: DbDep, user: UserDep):
    m = get_measure(db, measure_id)
    _visible(db, user, m)
    e = db.get(Evidence, evidence_id)
    if not e or e.measure_period.measure_id != m.id:
        raise HTTPException(404, "Файл не знайдено")
    if not storage.verify(e.object_key, e.sha256):
        raise HTTPException(409, "Перевірка цілісності не пройдена: збережений файл не відповідає своєму хешу")
    return Response(
        storage.get_object(e.object_key),
        media_type=storage.evidence_type(e.file_name) or "application/octet-stream",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(e.file_name)}", "X-Sha256": e.sha256,
                 "X-Content-Type-Options": "nosniff"},
    )


@router.get("/{measure_id}/history", response_model=list[s.AuditEntryOut])
def history(measure_id: uuid.UUID, db: DbDep, _: Admin):
    """Записи журналу дій по заходу, його періодах, файлах і прапорцях (лише для адміністратора)."""
    m = get_measure(db, measure_id)
    ids = [m.id] + [p.id for p in m.periods] + [e.id for p in m.periods for e in p.evidence] + [f.id for f in m.flags]
    rows = db.scalars(select(AuditLogEntry).where(AuditLogEntry.entity_id.in_(ids)).order_by(AuditLogEntry.id.desc()))
    return [entry_out(e) for e in rows]


@router.get("/{measure_id}/periods", response_model=list[s.MeasurePeriodOut])
def periods(measure_id: uuid.UUID, db: DbDep, user: UserDep):
    m = get_measure(db, measure_id)
    _visible(db, user, m)
    return db.scalars(select(MeasurePeriod).where(MeasurePeriod.measure_id == m.id).order_by(MeasurePeriod.period)).all()
