import uuid

from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from .. import audit
from ..auth import Coordinator, DbDep, UserDep
from ..config import today
from ..enums import KriDirection, RiskLevel
from ..models import CorruptionRisk, Indicator, IndicatorValue, OrgUnit, Program
from ..schemas import domain as s
from ..schemas.risk_model import IndicatorPatch, RiskReassessIn
from ..services import control, risk_model, scope
from ..services.mappers import indicator_out

router = APIRouter(tags=["Risks & Indicators"])


def _risk_out(r: CorruptionRisk) -> s.RiskOut:
    score = r.probability * r.impact if r.probability and r.impact else None
    return s.RiskOut(id=r.id, code=r.code, program_id=r.program_id, description=r.description, level=r.level,
                     probability=r.probability, impact=r.impact, score=score,
                     process=r.process or "", content=r.content or "", sources=r.sources or "",
                     existing_controls=r.existing_controls or "", owner_unit_id=r.owner_unit_id,
                     owner_unit_name=r.owner_unit.name if r.owner_unit else None, measure_count=len(r.measures),
                     indicators=[indicator_out(i) for i in r.indicators])


@router.get("/risks", response_model=list[s.RiskOut])
def list_risks(db: DbDep, user: UserDep):
    """Реєстр корупційних ризиків з індикаторами (виконавцю й керівнику підрозділу — лише ризики їхніх заходів)."""
    see = scope.of(db, user)
    return [_risk_out(r) for r in db.scalars(select(CorruptionRisk).order_by(CorruptionRisk.code)) if see.risk(r)]


@router.post("/risks", response_model=s.RiskOut, status_code=201)
def create_risk(data: s.RiskCreate, db: DbDep, user: Coordinator):
    """Запис реєстру корупційних ризиків (Методологія НАЗК; словник: ryzyky): бали ймовірності й наслідків ставить
    робоча група, рівень рахується з балу; індикатор ризику (KRI) — разом із ризиком."""
    if data.program_id is not None and db.get(Program, data.program_id) is None:
        raise HTTPException(422, "Програму не знайдено")
    if data.owner_unit_id is not None and db.get(OrgUnit, data.owner_unit_id) is None:
        raise HTTPException(422, "Підрозділ-власник ризику не знайдено")
    if db.scalar(select(CorruptionRisk).where(CorruptionRisk.code == data.code.strip())):
        raise HTTPException(409, f"Ризик з кодом {data.code.strip()} уже є в реєстрі")
    problem = risk_model.level_problem(data.level, data.probability, data.impact)
    if problem:
        raise HTTPException(422, problem)
    if data.indicator:
        _kri_check(data.indicator.baseline, data.indicator.target, data.indicator.direction)
    r = CorruptionRisk(**data.model_dump(exclude={"level", "indicator", "code"}), code=data.code.strip(),
                       level=data.level or RiskLevel.from_score(data.probability * data.impact))
    db.add(r)
    db.flush()
    audit.record(db, user, "corruption_risk", r.id, "create", None, data.model_dump(mode="json", exclude={"indicator"}))
    if data.indicator:
        i = Indicator(risk=r, weight=1, lag_months=6, **data.indicator.model_dump())
        db.add(i)
        db.flush()
        audit.record(db, user, "indicator", i.id, "create", None, data.indicator.model_dump(mode="json"))
    db.commit()
    db.refresh(r)
    return _risk_out(r)


@router.get("/risks/{risk_id}", response_model=s.RiskOut)
def get_risk(risk_id: uuid.UUID, db: DbDep, user: UserDep):
    r = db.get(CorruptionRisk, risk_id)
    if not r:
        raise HTTPException(404, "Ризик не знайдено")
    scope.of(db, user).ensure_risk(r)
    return _risk_out(r)


@router.patch("/risks/{risk_id}", response_model=s.RiskOut)
def reassess_risk(risk_id: uuid.UUID, data: RiskReassessIn, db: DbDep, user: Coordinator):
    """Переоцінка ризику робочою групою: нові ймовірність і наслідки з обовʼязковим обґрунтуванням.
    Рівень рахується з балу; система сама бал НАЗК не змінює — лише пропонує підстави (P1, L+1, L-1)."""
    r = db.get(CorruptionRisk, risk_id)
    if not r:
        raise HTTPException(404, "Ризик не знайдено")
    old = {"probability": r.probability, "impact": r.impact, "level": r.level.value}
    r.probability, r.impact = data.probability, data.impact
    r.level = RiskLevel.from_score(data.probability * data.impact)
    db.flush()
    audit.record(db, user, "corruption_risk", r.id, "reassess", old,
                 {"probability": r.probability, "impact": r.impact, "level": r.level.value,
                  "justification": data.justification})
    risk_model.evaluate_signals(db, today(), [r])
    db.commit()
    return _risk_out(r)


def _kri_check(baseline, target, direction: KriDirection | None) -> None:
    lower = None if direction is None else direction == KriDirection.LOWER
    problem = risk_model.kri_problem(baseline, target, lower)
    if problem:
        raise HTTPException(422, problem)


@router.get("/indicators", response_model=list[s.IndicatorOut])
def list_indicators(db: DbDep, user: UserDep):
    see = scope.of(db, user)
    return [indicator_out(i) for i in db.scalars(select(Indicator).order_by(Indicator.name)) if see.indicator(i)]


@router.post("/indicators", response_model=s.IndicatorOut, status_code=201)
def create_indicator(data: s.IndicatorIn, db: DbDep, user: Coordinator):
    _kri_check(data.baseline, data.target, data.direction)
    i = Indicator(**data.model_dump())
    db.add(i)
    db.flush()
    audit.record(db, user, "indicator", i.id, "create", None, data.model_dump())
    db.commit()
    db.refresh(i)
    return indicator_out(i)


def _indicator(db, indicator_id: uuid.UUID) -> Indicator:
    i = db.get(Indicator, indicator_id)
    if not i:
        raise HTTPException(404, "Індикатор не знайдено")
    return i


@router.patch("/indicators/{indicator_id}", response_model=s.IndicatorOut)
def patch_indicator(indicator_id: uuid.UUID, data: IndicatorPatch, db: DbDep, user: Coordinator):
    """Зміна KRI з обовʼязковим обґрунтуванням. Зміна бази чи цілі після затвердження дає сигнал B1."""
    i = _indicator(db, indicator_id)
    changes = data.model_dump(exclude_unset=True, exclude={"justification"})
    _kri_check(changes.get("baseline", i.baseline), changes.get("target", i.target),
               changes.get("direction", i.direction))
    old = {k: getattr(i, k) for k in changes}
    for k, v in changes.items():
        setattr(i, k, v)
    db.flush()
    audit.record(db, user, "indicator", i.id, "update", old, {**changes, "justification": data.justification})
    control.evaluate(db, today())
    risk_model.evaluate_signals(db, today())
    db.commit()
    db.refresh(i)
    return indicator_out(i)


@router.get("/indicators/{indicator_id}/values", response_model=list[s.IndicatorValueOut])
def list_values(indicator_id: uuid.UUID, db: DbDep, user: UserDep):
    i = _indicator(db, indicator_id)
    if not scope.of(db, user).indicator(i):
        raise HTTPException(403, "Індикатор поза вашою зоною відповідальності")
    return i.values


@router.post("/indicators/{indicator_id}/values", response_model=s.IndicatorOut, status_code=201)
def add_value(indicator_id: uuid.UUID, data: s.IndicatorValueIn, db: DbDep, user: Coordinator):
    """Нове значення індикатора (історія незмінна — лише додавання)."""
    i = _indicator(db, indicator_id)
    v = IndicatorValue(indicator=i, **data.model_dump())
    db.add(v)
    db.flush()
    audit.record(db, user, "indicator_value", v.id, "create", None, data.model_dump())
    control.evaluate(db, today())
    risk_model.evaluate_signals(db, today())
    control.generate_recommendations(db)
    db.commit()
    db.refresh(i)
    return indicator_out(i)
