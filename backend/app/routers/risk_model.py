import uuid
from datetime import date
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import select

from .. import audit
from ..auth import Coordinator, DbDep, Staff
from ..config import today
from ..enums import FlagStatus, RiskLevel
from ..models import CorruptionRisk, Incident, RiskSignal
from ..schemas import risk_model as s
from ..services import control, coverage, risk_model as rm, scope
from ..services.dashboards import resolve_program

router = APIRouter(prefix="/risk-model", tags=["Risk Model"])

ProgramQ = Annotated[uuid.UUID | None, Query(alias="programId")]
AsOfQ = Annotated[date | None, Query(alias="asOf", description="Дата розрахунку; за замовчуванням — сьогодні")]


def _r(x: float | None, nd: int = 4) -> float | None:
    return None if x is None else round(x, nd)


def signal_out(risk: CorruptionRisk, t, ind, facts, text, stored: RiskSignal | None = None) -> s.SignalOut:
    code, label, color = rm.SIGNAL_RULES[t]
    return s.SignalOut(
        id=stored.id if stored else None, risk_id=risk.id, risk_code=risk.code,
        indicator_id=ind.id if ind else None, indicator_name=ind.name if ind else None,
        type=t, rule_code=code, label=label, color=color, facts=facts, explanation=text,
        status=stored.status if stored else FlagStatus.OPEN, created_at=stored.created_at if stored else None,
    )


def assessment_out(a: rm.Assessment, see: scope.Scope | None = None) -> s.RiskAssessmentOut:
    r = a.risk
    kris = [
        s.KriOut(
            indicator_id=k.indicator.id, name=k.indicator.name, unit=k.indicator.unit,
            direction="LOWER" if k.indicator.lower_is_better else "HIGHER", weight=_r(k.weight),
            lag_months=k.indicator.lag_months, source=k.indicator.source or "", independent=k.indicator.independent,
            baseline=k.baseline, target=k.target, target_date=k.indicator.target_date, current=k.current,
            measured_at=k.measured_at, sample_size=k.sample_size, min_sample=k.indicator.min_sample,
            delta=_r(k.delta), change=_r(k.change), noise=k.noise, raw=_r(k.raw), p=_r(k.p),
            self_report_discount=k.self_report_discount, expected=_r(k.expected), state=k.state,
            state_label=rm.EFFECT_UA[k.state], insufficient=k.insufficient,
            paired_with=k.indicator.paired_with.name if k.indicator.paired_with else None,
            baseline_frozen_at=k.indicator.baseline_frozen_at,
            baseline_changed=bool(k.indicator.baseline_hash)
            and k.indicator.baseline_hash != k.indicator.baseline_digest(),
        )
        for k in a.kris
    ]
    measures = [
        s.MeasureStateOut(measure_id=x.measure.id, code=x.measure.code, title=x.measure.title,
                          section=x.measure.section.number, status=x.period.status if x.period else None,
                          done=x.done, pending=x.pending, completed_on=x.completed)
        for x in a.measures if see is None or see.measure(x.measure)
    ]
    label, color = rm.VERDICTS[a.verdict]
    return s.RiskAssessmentOut(
        risk_id=r.id, code=r.code, description=r.description, level=r.level, as_of=a.as_of,
        ruleset_version=rm.RULESET_VERSION, probability0=a.probability0, impact0=a.impact0,
        inherent=a.inherent, inherent_level=RiskLevel.from_score(a.inherent), kris=kris,
        rrs=_r(a.rrs), rrs_category=rm.rrs_category(a.rrs), expected=_r(a.expected), effect=a.effect,
        effect_label=rm.EFFECT_UA[a.effect], measures=measures, done_count=a.done_count,
        verdict=a.verdict, verdict_label=label, verdict_color=color, preliminary=a.preliminary,
        effect_due=a.effect_due,
        hints=[s.HintOut(rule=h.rule, text=h.text, suggested=h.suggested, inputs=h.inputs, source=h.source)
               for h in a.hints],
        signals=[signal_out(r, t, ind, facts, text) for t, ind, facts, text in a.signals],
        incidents=[s.IncidentOut.model_validate(i) for i in r.incidents],
    )


def _uncovered(r: CorruptionRisk) -> s.UncoveredRisk:
    l0, c0 = rm.base_scores(r)
    return s.UncoveredRisk(risk_id=r.id, code=r.code, description=r.description, level=r.level,
                           probability0=l0, impact0=c0, inherent=l0 * c0)


def _risk(db, risk_id: uuid.UUID) -> CorruptionRisk:
    r = db.get(CorruptionRisk, risk_id)
    if not r:
        raise HTTPException(404, "Ризик не знайдено")
    return r


@router.get("/overview", response_model=s.RiskModelOverview)
def overview(db: DbDep, user: Staff, program_id: ProgramQ = None, as_of: AsOfQ = None):
    """PRI, EXEC, FCG (розрив формального виконання), вердикти ризиків і найслабша ланка."""
    program = resolve_program(db, program_id)
    see = scope.of(db, user)
    pm = rm.program_metrics(db, program, as_of or today(), see)
    shares = {a.risk.id: a for a in pm.assessments}
    weights = sum(a.inherent for a in pm.assessments) or 1

    def brief(a: rm.Assessment | None) -> s.RiskBrief | None:
        if a is None:
            return None
        share = pm.shares.get(a.risk.id, 0.0)
        return s.RiskBrief(code=a.risk.code, rrs=_r(a.rrs),
                           contribution_pp=_r(a.inherent * (share - (a.rrs or 0)) / weights * 100, 2))

    return s.RiskModelOverview(
        program_id=program.id, as_of=pm.as_of, ruleset_version=rm.RULESET_VERSION,
        pri=_r(pm.pri), exec=_r(pm.exec), fcg=_r(pm.fcg_pp, 2), fcg_color=pm.color,
        top_contributor=brief(pm.top_contributor), weakest_link=brief(pm.weakest),
        sub_index=_r(pm.sub_index), sub_index_count=pm.sub_index_count,
        scope_name=None if see.whole_program else user.org_unit.name,
        verdict_counts=pm.verdict_counts,
        risks_with_done=sum(1 for a in pm.assessments if a.done_count),
        risks_working=sum(1 for a in pm.assessments if a.verdict == "WORKING"),
        uncovered=[_uncovered(r) for r in (db.get(CorruptionRisk, g.risk_id)
                                           for g in coverage.gaps(db, program, see) if g.rule_code == "C1")
                   if r.program_id in (None, program.id)],  # ризики інших програм — не прогалина цієї
        risks=[assessment_out(shares[a.risk.id], see) for a in pm.assessments],
    )


@router.get("/risks/{risk_id}", response_model=s.RiskAssessmentOut)
def risk_assessment(risk_id: uuid.UUID, db: DbDep, user: Staff, as_of: AsOfQ = None):
    """Один ризик: KRI (p, δ, n, очікуваний прогрес), вердикт «виконання × ефект» і підстави для переоцінки."""
    r = _risk(db, risk_id)
    see = scope.of(db, user)
    see.ensure_risk(r)
    return assessment_out(rm.assess(r, as_of or today()), see)


@router.get("/signals", response_model=list[s.SignalOut])
def signals(db: DbDep, user: Staff, status: FlagStatus | None = FlagStatus.OPEN):
    q = select(RiskSignal).order_by(RiskSignal.created_at.desc())
    if status:
        q = q.where(RiskSignal.status == status)
    see = scope.of(db, user)
    return [signal_out(x.risk, x.type, x.indicator, x.facts, x.explanation, x) for x in db.scalars(q) if see.risk(x.risk)]


@router.get("/risks/{risk_id}/incidents", response_model=list[s.IncidentOut])
def incidents(risk_id: uuid.UUID, db: DbDep, user: Staff):
    r = _risk(db, risk_id)
    scope.of(db, user).ensure_risk(r)
    return r.incidents


@router.post("/risks/{risk_id}/incidents", response_model=s.IncidentOut, status_code=201)
def add_incident(risk_id: uuid.UUID, data: s.IncidentIn, db: DbDep, user: Coordinator):
    """Підтверджений випадок реалізації ризику: дає підставу переоцінити ймовірність (P1: 6 / 12 / 36 міс.)."""
    r = _risk(db, risk_id)
    inc = Incident(risk_id=r.id, created_by=user.id, **data.model_dump())
    db.add(inc)
    db.flush()
    audit.record(db, user, "incident", inc.id, "create", None, {**data.model_dump(), "risk": r.code})
    db.refresh(r)
    rm.evaluate_signals(db, today())
    control.generate_recommendations(db)
    db.commit()
    return inc
