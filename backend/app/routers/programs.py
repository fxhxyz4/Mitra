import uuid

from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from ..auth import Coordinator, DbDep, Staff, UserDep
from ..config import today
from ..enums import MeasureStatus
from ..models import Program
from ..schemas import CoverageGap, domain as s
from ..services import control, coverage, measures as svc, scope
from ..services.mappers import measure_item

router = APIRouter(prefix="/programs", tags=["Program Register"])


def get_program(db, program_id: uuid.UUID) -> Program:
    p = db.get(Program, program_id)
    if not p:
        raise HTTPException(404, "Програму не знайдено")
    return p


@router.get("", response_model=list[s.ProgramOut])
def list_programs(db: DbDep, _: UserDep):
    return db.scalars(select(Program).order_by(Program.period_start.desc())).all()


@router.post("", response_model=s.ProgramOut, status_code=201)
def create_program(data: s.ProgramIn, db: DbDep, user: Coordinator):
    p = svc.create_program(db, user, data)
    db.commit()
    return p


@router.get("/{program_id}", response_model=s.ProgramOut)
def get_one(program_id: uuid.UUID, db: DbDep, _: UserDep):
    return get_program(db, program_id)


@router.get("/{program_id}/passport", response_model=s.ProgramPassport)
def passport(program_id: uuid.UUID, db: DbDep, user: UserDep):
    """Електронний паспорт: структура, цілі (ризики/індикатори), заходи, строки, відповідальні."""
    p = get_program(db, program_id)
    t = today()
    see = scope.of(db, user)
    sections = [
        s.SectionPassport(id=sec.id, number=sec.number, title=sec.title,
                          measures=[measure_item(m, t) for m in sec.measures if see.measure(m)])
        for sec in p.sections
    ]
    items = [m for sec in sections for m in sec.measures]
    totals = {"measures": len(items), "overdue": sum(m.is_overdue for m in items)}
    for st in MeasureStatus:
        totals[st.value] = sum(1 for m in items if m.status == st)
    return s.ProgramPassport(
        **s.ProgramOut.model_validate(p).model_dump(), org_unit_name=p.org_unit.name, sections=sections, totals=totals
    )


@router.post("/{program_id}/approve", response_model=s.ProgramOut)
def approve(program_id: uuid.UUID, db: DbDep, user: Coordinator):
    p = svc.approve_program(db, user, get_program(db, program_id), today())
    control.evaluate(db, today(), p.id)
    db.commit()
    return p


@router.get("/{program_id}/coverage", response_model=list[CoverageGap])
def program_coverage(program_id: uuid.UUID, db: DbDep, user: Staff) -> list[CoverageGap]:
    """Прогалини покриття за правилами: C1 ризик без заходів, C2 захід розділу 2 без ризику, C3 без індикатора."""
    return coverage.gaps(db, get_program(db, program_id), scope.of(db, user))
