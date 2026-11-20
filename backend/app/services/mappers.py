from datetime import date

from ..enums import EDITABLE_BY_EXECUTOR, FlagStatus, MeasureStatus, Role
from ..models import Indicator, Measure, MeasurePeriod, RiskFlag, User
from ..schemas import domain as s


def indicator_out(ind: Indicator) -> s.IndicatorOut:
    return s.IndicatorOut(
        id=ind.id,
        name=ind.name,
        unit=ind.unit,
        baseline=ind.baseline,
        target=ind.target,
        risk_id=ind.risk_id,
        direction=ind.direction,
        weight=ind.weight if ind.weight is not None else 1,
        lag_months=ind.lag_months if ind.lag_months is not None else 6,
        source=ind.source or "",
        independent=ind.independent if ind.independent is not None else True,
        min_sample=ind.min_sample,
        noise_threshold=ind.noise_threshold,
        target_date=ind.target_date,
        paired_with_id=ind.paired_with_id,
        baseline_frozen_at=ind.baseline_frozen_at,
        current=ind.current,
        is_improved=ind.is_improved(),
        is_target_reached=ind.is_target_reached(),
        values=[s.IndicatorValueOut.model_validate(v) for v in ind.values],
    )


def flag_out(f: RiskFlag) -> s.RiskFlagOut:
    return s.RiskFlagOut(
        id=f.id,
        measure_id=f.measure_id,
        measure_code=f.measure.code,
        measure_title=f.measure.title,
        type=f.type,
        rule_code=f.rule_code,
        facts=f.facts,
        explanation=f.explain(),
        status=f.status,
        created_at=f.created_at,
        resolved_at=f.resolved_at,
        resolution_comment=f.resolution_comment,
    )


def user_ref(u: User | None) -> s.UserRef | None:
    return s.UserRef.model_validate(u) if u else None


def resolve_period(m: Measure, today: date, period: str | None = None) -> MeasurePeriod | None:
    if period:
        return next((p for p in m.periods if p.period == period), None)
    return m.period_for(today)


def measure_item(m: Measure, today: date) -> s.MeasureListItem:
    p = m.period_for(today)
    deadline = m.deadline_for(p) if p else m.planned_deadline
    resp = m.responsible or (m.assignments[0] if m.assignments else None)
    return s.MeasureListItem(
        id=m.id,
        code=m.code,
        title=m.title,
        section_number=m.section.number,
        is_permanent=m.is_permanent,
        planned_deadline=m.planned_deadline,
        deadline=deadline,
        period=p.period if p else None,
        status=p.status if p else None,
        is_overdue=m.is_overdue(today),
        days_left=(deadline - today).days,
        risk=s.RiskRef.model_validate(m.risk) if m.risk else None,
        responsible_unit=resp.org_unit.name if resp else None,
        responsible_user=resp.user.display_name if resp and resp.user else None,
        open_flags=[
            s.FlagBrief(id=f.id, type=f.type, explanation=f.explanation, status=f.status)
            for f in m.flags
            if f.status == FlagStatus.OPEN
        ],
        evidence_count=len(p.evidence) if p else 0,
    )


def allowed_actions(m: Measure, p: MeasurePeriod | None, user: User, assigned: bool) -> list[str]:
    if p is None:
        return []
    acts: list[str] = []
    if user.role == Role.EXECUTOR and assigned and p.status in EDITABLE_BY_EXECUTOR:
        acts += ["progress", "submit", "uploadEvidence"]
    if user.role == Role.COORDINATOR:
        acts.append("edit")
        own = any(u.author_id == user.id and u.status_to == MeasureStatus.ON_REVIEW for u in p.updates)
        if p.status == MeasureStatus.ON_REVIEW and not own:
            acts += ["approve", "return"]
    return acts


def measure_detail(m: Measure, today: date, user: User, assigned: bool, period: str | None = None) -> s.MeasureDetail:
    base = measure_item(m, today)
    p = resolve_period(m, today, period)
    return s.MeasureDetail(
        **base.model_dump(),
        section_title=m.section.title,
        program_id=m.section.program_id,
        required_evidence=m.required_evidence,
        indicator_text=m.indicator_text or (m.indicator.name if m.indicator else ""),
        indicator=indicator_out(m.indicator) if m.indicator else None,
        internal_deadline=m.internal_deadline,
        deadline_changes=[
            s.DeadlineChangeOut(id=c.id, decided_on=c.decided_on, old_deadline=c.old_deadline,
                                new_deadline=c.new_deadline, reason=c.reason, created_at=c.created_at,
                                decided_by_name=c.author.display_name if c.author else None)
            for c in m.deadline_changes
        ],
        assignments=[
            s.AssignmentOut(
                org_unit_id=a.org_unit_id,
                user_id=a.user_id,
                is_responsible=a.is_responsible,
                org_unit_name=a.org_unit.name,
                user_name=a.user.display_name if a.user else None,
            )
            for a in m.assignments
        ],
        periods=[s.MeasurePeriodOut.model_validate(x) for x in m.periods],
        current_period=s.MeasurePeriodOut.model_validate(p) if p else None,
        updates=[
            s.ProgressUpdateOut(
                id=u.id,
                status_from=u.status_from,
                status_to=u.status_to,
                text=u.body,
                created_at=u.created_at,
                author=user_ref(u.author),
            )
            for u in (p.updates if p else [])
        ],
        approvals=[
            s.ApprovalOut(
                id=a.id, decision=a.decision, comment=a.comment, created_at=a.created_at, reviewer=user_ref(a.reviewer)
            )
            for a in (p.approvals if p else [])
        ],
        evidence=[evidence_out(e, p.period) for e in (p.evidence if p else [])],
        flags=[flag_out(f) for f in m.flags],
        allowed_actions=allowed_actions(m, p, user, assigned),
    )


def evidence_out(e, period: str) -> s.EvidenceOut:
    return s.EvidenceOut(
        id=e.id,
        period=period,
        file_name=e.file_name,
        content_type=e.content_type,
        size=e.size,
        object_key=e.object_key,
        sha256=e.sha256,
        version=e.version,
        uploaded_at=e.uploaded_at,
        doc_type=e.doc_type or "",
        document_date=e.document_date,
        uploaded_by=e.uploaded_by,
    )
