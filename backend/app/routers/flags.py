import uuid
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import select

from ..auth import Coordinator, DbDep, UserDep, require_roles
from ..config import today
from ..enums import FlagStatus, FlagType, Role
from ..models import Measure, RiskFlag, Section
from ..schemas import domain as s
from ..services import control, scope
from ..services.mappers import flag_out

router = APIRouter(prefix="/flags", tags=["Risk Flags"])


@router.get("", response_model=list[s.RiskFlagOut])
def list_flags(
    db: DbDep,
    user: UserDep,
    status: FlagStatus | None = FlagStatus.OPEN,
    type: FlagType | None = None,
    program_id: Annotated[uuid.UUID | None, Query(alias="programId")] = None,
    measure_id: Annotated[uuid.UUID | None, Query(alias="measureId")] = None,
):
    """Координатор, керівник, аналітик — усі; виконавець — лише щодо власних заходів."""
    require_roles(Role.COORDINATOR, Role.HEAD, Role.ANALYST, Role.EXECUTOR)(user)
    q = select(RiskFlag).join(RiskFlag.measure).join(Measure.section)
    if status:
        q = q.where(RiskFlag.status == status)
    if type:
        q = q.where(RiskFlag.type == type)
    if program_id:
        q = q.where(Section.program_id == program_id)
    if measure_id:
        q = q.where(RiskFlag.measure_id == measure_id)
    flags = db.scalars(q.order_by(RiskFlag.created_at.desc())).all()
    see = scope.of(db, user)
    return [flag_out(f) for f in flags if see.measure(f.measure)]


@router.post("/{flag_id}/resolve", response_model=s.RiskFlagOut)
def resolve(flag_id: uuid.UUID, data: s.ResolveIn, db: DbDep, user: UserDep):
    """Зняти прапорець з коментарем. FORMAL_CLOSURE знімає лише керівник."""
    f = db.get(RiskFlag, flag_id)
    if not f:
        raise HTTPException(404, "Прапорець не знайдено")
    scope.of(db, user).ensure_measure(f.measure)
    control.resolve_flag(db, user, f, data.comment)
    db.commit()
    return flag_out(f)


@router.post("/evaluate", response_model=s.JobResult)
def run_now(db: DbDep, _: Coordinator):
    """Запустити щоденну задачу (06:00) вручну: старт періодів, правила, рекомендації, нагадування."""
    return control.run_daily(db, today())
