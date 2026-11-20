import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select

from ..auth import DbDep, UserDep, require_roles
from ..config import today
from ..enums import Role
from ..models import Reminder
from ..schemas import domain as s
from ..services import dashboards as d, scope

router = APIRouter(tags=["Dashboards"])

ProgramQ = Annotated[uuid.UUID | None, Query(alias="programId")]
Executor = Depends(require_roles(Role.EXECUTOR))
Coord = Depends(require_roles(Role.COORDINATOR, Role.HEAD, Role.ANALYST))
Exec = Depends(require_roles(Role.HEAD, Role.ANALYST))


@router.get("/dashboard/executor", response_model=d.ExecutorDashboard)
def executor(db: DbDep, user: UserDep, _=Executor):
    """Кабінет виконавця: мої заходи на 30 днів, повернені, прострочені, нагадування."""
    return d.executor(db, user, today())


@router.get("/dashboard/coordinator", response_model=d.CoordinatorDashboard, dependencies=[Coord])
def coordinator(db: DbDep, user: UserDep, program_id: ProgramQ = None):
    """Панель координатора: черга на перевірку, Risk Flags, прогрес за розділами, календар, готовність звіту."""
    return d.coordinator(db, d.resolve_program(db, program_id), today(), scope.of(db, user))


@router.get("/dashboard/executive", response_model=d.ExecutiveDashboard, dependencies=[Exec])
def executive(db: DbDep, user: UserDep, program_id: ProgramQ = None):
    """Executive Dashboard: стан програми, критичні заходи, ризики до/після, карта підрозділів, рекомендації."""
    return d.executive(db, d.resolve_program(db, program_id), today(), scope.of(db, user))


@router.get("/dashboard/units/{org_unit_id}", response_model=d.UnitDashboard, dependencies=[Exec])
def unit(org_unit_id: uuid.UUID, db: DbDep, user: UserDep, program_id: ProgramQ = None):
    see = scope.of(db, user)
    if not see.unit(org_unit_id):
        raise HTTPException(403, "Підрозділ поза вашою зоною відповідальності")
    return d.unit(db, d.resolve_program(db, program_id), org_unit_id, today())


@router.get("/reminders", response_model=list[s.ReminderOut])
def my_reminders(db: DbDep, user: UserDep, include_future: Annotated[bool, Query(alias="includeFuture")] = False):
    q = select(Reminder).where(Reminder.user_id == user.id)
    if not include_future:
        q = q.where(Reminder.sent.is_(True))
    return [d.reminder_out(r) for r in db.scalars(q.order_by(Reminder.send_at.desc()))]
